"""Named result anchors: CRUD, resolution, refresh, staleness, macros.

Also exposes the cross-partition facade ``ResultAnchorService`` /
``ResultAnchorInfo`` consumed by the writing partition (anchor insertion and
macros regeneration), plus the pure ``render_macros_tex`` re-export.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError
from researchos.common.roles import ProjectRole
from researchos.experiments.directions import dedupe_points, metric_direction, reduce_series
from researchos.experiments.models import Experiment, ExperimentRun
from researchos.experiments.repository import (
    ExperimentRepository,
    MetricRepository,
    RunRepository,
)
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .events import publish_anchor_values_updated
from .macros import (
    UNRESOLVED_VALUE,
    ResolvedAnchor,
    format_anchor_value,
    macro_name,
    render_macros_tex,
)
from .models import ResultAnchor
from .repository import AnchorRepository
from .schemas import (
    AnchorStalenessItem,
    AnchorStalenessResponse,
    CreateAnchorRequest,
    RefreshAnchorsResponse,
    RefreshedAnchorItem,
    UpdateAnchorRequest,
)

__all__ = [
    "AnchorService",
    "ResultAnchorInfo",
    "ResultAnchorService",
    "render_macros_tex",
]

# Fields whose change invalidates the captured snapshot.
_SOURCE_FIELDS = ("experiment_id", "run_id", "metric_name", "aggregation")

# Fixed path the writing partition materializes macros into (CONSOLIDATION 搂5).
ANCHORS_FILE_PATH = "results/anchors.tex"


class AnchorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.anchors = AnchorRepository(db)
        self.experiments = ExperimentRepository(db)
        self.runs = RunRepository(db)
        self.metrics = MetricRepository(db)
        self.projects = ProjectService(db)

    # --- CRUD ----------------------------------------------------------------
    async def create_anchor(
        self, actor: User, project_id: uuid.UUID, payload: CreateAnchorRequest
    ) -> ResultAnchor:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        await self._validate_source(
            project_id, experiment_id=payload.experiment_id, run_id=payload.run_id
        )
        if await self.anchors.get_by_name(project_id, payload.name) is not None:
            raise ConflictError("An anchor with this name already exists.")
        anchor = await self.anchors.add(
            ResultAnchor(
                project_id=project_id,
                name=payload.name,
                experiment_id=payload.experiment_id,
                run_id=payload.run_id,
                metric_name=payload.metric_name,
                aggregation=payload.aggregation,
                decimals=payload.decimals,
                scale=payload.scale,
                suffix=payload.suffix,
                created_by=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(anchor)
        return anchor

    async def list_anchors(self, actor: User, project_id: uuid.UUID) -> list[ResultAnchor]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.anchors.list_by_project(project_id)

    async def get_anchor(
        self, actor: User, project_id: uuid.UUID, anchor_id: uuid.UUID
    ) -> ResultAnchor:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        anchor = await self.anchors.get(project_id, anchor_id)
        if anchor is None:
            raise NotFoundError("Anchor not found.")
        return anchor

    async def update_anchor(
        self, actor: User, project_id: uuid.UUID, anchor_id: uuid.UUID, payload: UpdateAnchorRequest
    ) -> ResultAnchor:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        anchor = await self.anchors.get(project_id, anchor_id)
        if anchor is None:
            raise NotFoundError("Anchor not found.")

        fields = payload.model_fields_set
        if "name" in fields and payload.name is not None and payload.name != anchor.name:
            if await self.anchors.get_by_name(project_id, payload.name) is not None:
                raise ConflictError("An anchor with this name already exists.")
            anchor.name = payload.name

        experiment_id = (
            payload.experiment_id
            if "experiment_id" in fields and payload.experiment_id is not None
            else anchor.experiment_id
        )
        run_id = payload.run_id if "run_id" in fields else anchor.run_id
        await self._validate_source(project_id, experiment_id=experiment_id, run_id=run_id)

        source_changed = False
        for field in _SOURCE_FIELDS:
            if field not in fields:
                continue
            value = getattr(payload, field)
            if field == "experiment_id" and value is None:
                continue
            if field == "aggregation" and value is None:
                continue
            if field == "metric_name" and value is None:
                continue
            if getattr(anchor, field) != value:
                setattr(anchor, field, value)
                source_changed = True
        if "decimals" in fields and payload.decimals is not None:
            anchor.decimals = payload.decimals
        if "scale" in fields and payload.scale is not None:
            anchor.scale = payload.scale
        if "suffix" in fields and payload.suffix is not None:
            anchor.suffix = payload.suffix

        if source_changed:
            anchor.captured_value = None
            anchor.captured_run_id = None
            anchor.captured_at = None
            anchor.stale = False

        await self.db.commit()
        await self.db.refresh(anchor)
        return anchor

    async def delete_anchor(self, actor: User, project_id: uuid.UUID, anchor_id: uuid.UUID) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        anchor = await self.anchors.get(project_id, anchor_id)
        if anchor is None:
            raise NotFoundError("Anchor not found.")
        await self.anchors.delete(anchor)
        await self.db.commit()

    async def _validate_source(
        self, project_id: uuid.UUID, *, experiment_id: uuid.UUID, run_id: uuid.UUID | None
    ) -> None:
        exp = await self.experiments.get(project_id, experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        if run_id is not None:
            run = await self.runs.get(project_id, run_id)
            if run is None or run.experiment_id != experiment_id:
                raise NotFoundError("Run not found.")

    # --- resolution ----------------------------------------------------------
    async def _resolve(
        self, anchor: ResultAnchor, *, experiment: Experiment | None = None
    ) -> ResolvedAnchor:
        if experiment is None:
            experiment = await self.db.get(Experiment, anchor.experiment_id)
        experiment_name = experiment.name if experiment else ""
        metric_meta = experiment.metric_meta_json if experiment else {}

        pinned = anchor.run_id is not None
        run: ExperimentRun | None = None
        if pinned:
            run = await self.db.get(ExperimentRun, anchor.run_id)
        else:
            run = await self.runs.latest_completed(anchor.experiment_id)
        run_label = run.name if (pinned and run is not None) else "latest"

        value: float | None = None
        if run is not None:
            rows = await self.metrics.series(run.id, anchor.metric_name)
            points = dedupe_points(rows)
            direction = metric_direction(anchor.metric_name, metric_meta)
            value = reduce_series(points, aggregation=anchor.aggregation, direction=direction)

        resolved = value is not None
        formatted = (
            format_anchor_value(
                value, decimals=anchor.decimals, scale=anchor.scale, suffix=anchor.suffix
            )
            if value is not None
            else UNRESOLVED_VALUE
        )
        return ResolvedAnchor(
            anchor_id=anchor.id,
            name=anchor.name,
            experiment_id=anchor.experiment_id,
            experiment_name=experiment_name,
            run_id=run.id if (run is not None and resolved) else None,
            pinned=pinned,
            run_label=run_label,
            metric_name=anchor.metric_name,
            aggregation=anchor.aggregation.value,
            value=value,
            formatted=formatted,
            resolved=resolved,
        )

    async def _resolve_all(
        self, project_id: uuid.UUID
    ) -> list[tuple[ResultAnchor, ResolvedAnchor]]:
        pairs: list[tuple[ResultAnchor, ResolvedAnchor]] = []
        for anchor in await self.anchors.list_by_project(project_id):
            pairs.append((anchor, await self._resolve(anchor)))
        return pairs

    def _capture(self, anchor: ResultAnchor, resolved: ResolvedAnchor, *, now: datetime) -> None:
        anchor.captured_value = resolved.value
        anchor.captured_run_id = resolved.run_id
        anchor.captured_at = now
        anchor.stale = False

    # --- refresh / staleness / macros ---------------------------------------
    async def refresh_all(self, actor: User, project_id: uuid.UUID) -> RefreshAnchorsResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        pairs = await self._resolve_all(project_id)
        now = datetime.now(tz=UTC)
        items: list[RefreshedAnchorItem] = []
        for anchor, resolved in pairs:
            self._capture(anchor, resolved, now=now)
            items.append(
                RefreshedAnchorItem(
                    id=anchor.id,
                    name=anchor.name,
                    value=resolved.value,
                    formatted=resolved.formatted,
                    run_id=resolved.run_id,
                    resolved=resolved.resolved,
                )
            )
        await self.db.commit()
        unresolved = sum(1 for item in items if not item.resolved)
        await publish_anchor_values_updated(
            project_id=project_id,
            updated_count=len(items),
            stale_count=0,
            anchor_ids=[str(item.id) for item in items],
        )
        return RefreshAnchorsResponse(
            refreshed=len(items) - unresolved, unresolved=unresolved, anchors=items
        )

    async def _latest_value(
        self, anchor: ResultAnchor, experiment: Experiment | None
    ) -> tuple[uuid.UUID | None, float | None]:
        """Reduce the anchor's metric on the experiment's latest COMPLETED run."""

        latest = await self.runs.latest_completed(anchor.experiment_id)
        if latest is None:
            return None, None
        rows = await self.metrics.series(latest.id, anchor.metric_name)
        points = dedupe_points(rows)
        direction = metric_direction(
            anchor.metric_name, experiment.metric_meta_json if experiment else {}
        )
        value = reduce_series(points, aggregation=anchor.aggregation, direction=direction)
        return latest.id, value

    async def staleness_report(
        self, actor: User, project_id: uuid.UUID
    ) -> AnchorStalenessResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        items: list[AnchorStalenessItem] = []
        experiments: dict[uuid.UUID, Experiment | None] = {}
        for anchor in await self.anchors.list_by_project(project_id):
            if anchor.experiment_id not in experiments:
                experiments[anchor.experiment_id] = await self.db.get(
                    Experiment, anchor.experiment_id
                )
            latest_run_id, latest_value = await self._latest_value(
                anchor, experiments[anchor.experiment_id]
            )
            captured = anchor.captured_at is not None
            stale = captured and (
                latest_run_id != anchor.captured_run_id or latest_value != anchor.captured_value
            )
            delta: float | None = None
            delta_pct: float | None = None
            if captured and anchor.captured_value is not None and latest_value is not None:
                delta = latest_value - anchor.captured_value
                if anchor.captured_value != 0:
                    delta_pct = round(delta / abs(anchor.captured_value) * 100, 2)
            items.append(
                AnchorStalenessItem(
                    anchor_id=anchor.id,
                    name=anchor.name,
                    stale=bool(stale),
                    captured_run_id=anchor.captured_run_id,
                    captured_value=anchor.captured_value,
                    latest_run_id=latest_run_id,
                    latest_value=latest_value,
                    delta=delta,
                    delta_pct=delta_pct,
                )
            )
        return AnchorStalenessResponse(
            stale_count=sum(1 for item in items if item.stale), items=items
        )

    async def macros_tex(self, actor: User, project_id: uuid.UUID, *, refresh: bool) -> str:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        pairs = await self._resolve_all(project_id)
        now = datetime.now(tz=UTC)
        if refresh:
            for anchor, resolved in pairs:
                self._capture(anchor, resolved, now=now)
            await self.db.commit()
            resolved_list = [resolved for _, resolved in pairs]
        else:
            # Render from stored snapshots only.
            resolved_list = [self._resolved_from_snapshot(anchor) for anchor, _ in pairs]
        return render_macros_tex(resolved_list, project_id=project_id, generated_at=now)

    def _resolved_from_snapshot(self, anchor: ResultAnchor) -> ResolvedAnchor:
        value = anchor.captured_value
        resolved = value is not None
        return ResolvedAnchor(
            anchor_id=anchor.id,
            name=anchor.name,
            experiment_id=anchor.experiment_id,
            experiment_name="",
            run_id=anchor.captured_run_id,
            pinned=anchor.run_id is not None,
            run_label="latest" if anchor.run_id is None else "pinned",
            metric_name=anchor.metric_name,
            aggregation=anchor.aggregation.value,
            value=value,
            formatted=(
                format_anchor_value(
                    value, decimals=anchor.decimals, scale=anchor.scale, suffix=anchor.suffix
                )
                if value is not None
                else UNRESOLVED_VALUE
            ),
            resolved=resolved,
        )

    # --- run-completion hook (internal; same transaction, no commit) ---------
    async def mark_stale_for_experiment(self, experiment_id: uuid.UUID) -> list[uuid.UUID]:
        """Flag captured anchors whose resolution moved. Returns flagged ids."""

        anchors = await self.anchors.list_for_experiment(experiment_id)
        if not anchors:
            return []
        experiment = await self.db.get(Experiment, experiment_id)
        flagged: list[uuid.UUID] = []
        for anchor in anchors:
            if anchor.captured_at is None or anchor.stale:
                continue  # never captured -> nothing to be stale against
            resolved = await self._resolve(anchor, experiment=experiment)
            if anchor.run_id is not None:
                # Pinned: stale once a COMPLETED run newer than the captured one exists.
                latest = await self.runs.latest_completed(experiment_id)
                if latest is not None and latest.id != anchor.captured_run_id:
                    anchor.stale = True
                    flagged.append(anchor.id)
            elif (
                resolved.run_id != anchor.captured_run_id
                or resolved.value != anchor.captured_value
            ):
                anchor.stale = True
                flagged.append(anchor.id)
        return flagged


# --- Cross-partition facade (writing partition import surface) ---------------


@dataclass(frozen=True)
class ResultAnchorInfo:
    macro_name: str  # "ROS<name>", no backslash
    anchors_file_path: str  # fixed "results/anchors.tex"
    formatted_value: str
    experiment_id: uuid.UUID
    run_id: uuid.UUID | None


class ResultAnchorService:
    """Thin adapter over ``AnchorRepository`` + the macro renderer.

    ``latex_project_id`` is part of the interface for forward compatibility;
    anchors are project-scoped so it does not affect lookups today.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._service = AnchorService(db)

    @staticmethod
    def _anchor_name(name: str) -> str:
        return name[3:] if name.startswith("ROS") else name

    async def get_anchor(
        self, project_id: uuid.UUID, latex_project_id: uuid.UUID | None, macro: str
    ) -> ResultAnchorInfo | None:
        anchor = await self._service.anchors.get_by_name(project_id, self._anchor_name(macro))
        if anchor is None:
            return None
        resolved = await self._service._resolve(anchor)
        return self._info(anchor, resolved)

    async def list_anchors(
        self, project_id: uuid.UUID, latex_project_id: uuid.UUID | None = None
    ) -> list[ResultAnchorInfo]:
        infos: list[ResultAnchorInfo] = []
        for anchor, resolved in await self._service._resolve_all(project_id):
            infos.append(self._info(anchor, resolved))
        return infos

    async def render_macros(self, project_id: uuid.UUID) -> str:
        """Current macros.tex content (no snapshot capture) for regeneration."""

        pairs = await self._service._resolve_all(project_id)
        return render_macros_tex(
            [resolved for _, resolved in pairs],
            project_id=project_id,
            generated_at=datetime.now(tz=UTC),
        )

    @staticmethod
    def _info(anchor: ResultAnchor, resolved: ResolvedAnchor) -> ResultAnchorInfo:
        return ResultAnchorInfo(
            macro_name=macro_name(anchor.name),
            anchors_file_path=ANCHORS_FILE_PATH,
            formatted_value=resolved.formatted,
            experiment_id=anchor.experiment_id,
            run_id=resolved.run_id,
        )
