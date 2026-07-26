"""Figure business logic: CRUD, data resolution, rendering, staleness."""

from __future__ import annotations

import asyncio
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import fmean
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import (
    ConflictError,
    DependencyError,
    NotFoundError,
    ValidationError,
)
from researchos.common.hashing import sha256_hex
from researchos.common.rate_limit import enforce_rate_limit
from researchos.common.roles import ProjectRole
from researchos.experiments.directions import dedupe_points
from researchos.experiments.enums import ExperimentRunStatus
from researchos.experiments.models import ExperimentArtifact, ExperimentRun
from researchos.experiments.repository import (
    ArtifactRepository,
    ExperimentRepository,
    MetricRepository,
    RunRepository,
)
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .dispatch import dispatch_figure_render
from .enums import FigureRenderStatus
from .events import publish_figure_event
from .models import Figure, FigureAsset
from .presets import DEFAULT_STYLE_SLUG, PRESETS, StylePreset
from .render import render_figure_bytes
from .repository import FigureAssetRepository, FigureRepository
from .schemas import (
    CreateFigureRequest,
    RenderedAssetInfo,
    RenderFigureResponse,
    UpdateFigureRequest,
)
from .spec import FigureSpecModel, InlineSource, RunMetricSource

logger = structlog.get_logger(__name__)

MAX_ASSET_BYTES = 4 * 1024 * 1024
MAX_RENDER_POINTS_PER_SERIES = 1000
MAX_SYNC_SERIES = 4
MAX_SYNC_POINTS = 2000
SYNC_RENDER_TIMEOUT_SECONDS = 15.0
SYNC_RENDER_RATE_LIMIT = 10

Point = tuple[float, float]


@dataclass
class _PreparedRender:
    spec: FigureSpecModel
    series_data: list[list[Point]]
    labels: list[str | None]
    run_ids: list[uuid.UUID]
    total_points: int
    preset: StylePreset
    opts: dict[str, Any]


class FigureService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.figures = FigureRepository(db)
        self.assets = FigureAssetRepository(db)
        self.experiments = ExperimentRepository(db)
        self.runs = RunRepository(db)
        self.metrics = MetricRepository(db)
        self.artifacts = ArtifactRepository(db)
        self.projects = ProjectService(db)

    # --- CRUD ----------------------------------------------------------------
    async def create_figure(
        self, actor: User, project_id: uuid.UUID, payload: CreateFigureRequest
    ) -> Figure:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        await self._validate_spec_refs(project_id, payload.spec)
        if await self.figures.get_by_name(project_id, payload.name) is not None:
            raise ConflictError("A figure with this name already exists.")
        figure = await self.figures.add(
            Figure(
                project_id=project_id,
                name=payload.name,
                spec_json=payload.spec.model_dump(mode="json"),
                created_by=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(figure)
        return figure

    async def list_figures(self, actor: User, project_id: uuid.UUID) -> list[Figure]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.figures.list_by_project(project_id)

    async def get_figure(self, actor: User, project_id: uuid.UUID, figure_id: uuid.UUID) -> Figure:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        figure = await self.figures.get(project_id, figure_id)
        if figure is None:
            raise NotFoundError("Figure not found.")
        return figure

    def style_outdated(self, figure: Figure) -> bool:
        """Registry drift check; computed on read, never written on GET."""

        if figure.rendered_style_slug is None:
            return False
        preset = PRESETS.get(figure.rendered_style_slug)
        return preset is None or preset.version != figure.rendered_style_version

    async def update_figure(
        self, actor: User, project_id: uuid.UUID, figure_id: uuid.UUID, payload: UpdateFigureRequest
    ) -> Figure:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        figure = await self.figures.get(project_id, figure_id)
        if figure is None:
            raise NotFoundError("Figure not found.")
        fields = payload.model_fields_set

        if "name" in fields and payload.name is not None and payload.name != figure.name:
            if await self.figures.get_by_name(project_id, payload.name) is not None:
                raise ConflictError("A figure with this name already exists.")
            figure.name = payload.name
        if "spec" in fields and payload.spec is not None:
            await self._validate_spec_refs(project_id, payload.spec)
            figure.spec_json = payload.spec.model_dump(mode="json")
            figure.status = FigureRenderStatus.PENDING
            figure.stale = False
            figure.last_error = None
        if "latex_project_id" in fields:
            if payload.latex_project_id is not None:
                await self._validate_latex_project(project_id, payload.latex_project_id)
            figure.latex_project_id = payload.latex_project_id
        if "usage_path" in fields:
            figure.usage_path = payload.usage_path

        await self.db.commit()
        await self.db.refresh(figure)
        return figure

    async def delete_figure(self, actor: User, project_id: uuid.UUID, figure_id: uuid.UUID) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        figure = await self.figures.get(project_id, figure_id)
        if figure is None:
            raise NotFoundError("Figure not found.")
        await self.figures.delete(figure)
        await self.db.commit()

    async def _validate_latex_project(
        self, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> None:
        from researchos.documents.models import LatexProject

        latex_project = await self.db.get(LatexProject, latex_project_id)
        if latex_project is None or latex_project.project_id != project_id:
            raise NotFoundError("LaTeX project not found.")

    async def _validate_spec_refs(self, project_id: uuid.UUID, spec: FigureSpecModel) -> None:
        """Every referenced run/experiment must belong to the figure's project."""

        for series in spec.series:
            source = series.source
            if not isinstance(source, RunMetricSource):
                continue
            run: ExperimentRun | None = None
            if source.run_id is not None:
                run = await self.runs.get(project_id, source.run_id)
                if run is None:
                    raise NotFoundError("Run not found.")
            if source.experiment_id is not None:
                exp = await self.experiments.get(project_id, source.experiment_id)
                if exp is None:
                    raise NotFoundError("Experiment not found.")
                if run is not None and run.experiment_id != source.experiment_id:
                    raise NotFoundError("Run not found.")

    # --- rendering -----------------------------------------------------------
    async def render(
        self, actor: User, project_id: uuid.UUID, figure_id: uuid.UUID, *, mode: str
    ) -> RenderFigureResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        figure = await self.figures.get(project_id, figure_id)
        if figure is None:
            raise NotFoundError("Figure not found.")
        if mode == "sync":
            return await self._render_sync(actor, figure)
        return await self._render_async(actor, figure)

    async def _render_sync(self, actor: User, figure: Figure) -> RenderFigureResponse:
        spec = FigureSpecModel.model_validate(figure.spec_json)
        if len(spec.series) > MAX_SYNC_SERIES:
            raise ValidationError(
                "Figure exceeds synchronous render caps.", code="figure_too_large_for_sync"
            )
        await enforce_rate_limit(f"figure_sync:{actor.id}", limit=SYNC_RENDER_RATE_LIMIT)
        prepared = await self._prepare_render(figure)
        if prepared.total_points > MAX_SYNC_POINTS:
            raise ValidationError(
                "Figure exceeds synchronous render caps.", code="figure_too_large_for_sync"
            )
        assets = await self._execute_render(
            figure, prepared, timeout=SYNC_RENDER_TIMEOUT_SECONDS
        )
        await self._publish_completed(figure, prepared)
        return RenderFigureResponse(
            figure_id=figure.id, status=FigureRenderStatus.RENDERED, assets=assets
        )

    async def _render_async(self, actor: User, figure: Figure) -> RenderFigureResponse:
        if figure.status == FigureRenderStatus.RENDERING:
            raise ConflictError("Figure is already rendering.")
        figure.status = FigureRenderStatus.PENDING
        await self.db.commit()
        try:
            dispatch_figure_render(str(figure.id))
        except Exception as exc:  # broker down -> capped sync fallback
            if not _is_broker_error(exc):
                raise
            logger.warning("figure_dispatch_failed", figure_id=str(figure.id), error=str(exc))
            spec = FigureSpecModel.model_validate(figure.spec_json)
            if len(spec.series) > MAX_SYNC_SERIES:
                raise DependencyError(
                    "Figure worker is unavailable.", code="worker_unavailable"
                ) from exc
            await enforce_rate_limit(f"figure_sync:{actor.id}", limit=SYNC_RENDER_RATE_LIMIT)
            prepared = await self._prepare_render(figure)
            if prepared.total_points > MAX_SYNC_POINTS:
                raise DependencyError(
                    "Figure worker is unavailable.", code="worker_unavailable"
                ) from exc
            assets = await self._execute_render(
                figure, prepared, timeout=SYNC_RENDER_TIMEOUT_SECONDS
            )
            await self._publish_completed(figure, prepared)
            return RenderFigureResponse(
                figure_id=figure.id, status=FigureRenderStatus.RENDERED, assets=assets
            )
        await publish_figure_event(
            event_type="figure.render.queued",
            project_id=figure.project_id,
            figure_id=figure.id,
            payload={"figure_id": str(figure.id), "name": figure.name},
        )
        return RenderFigureResponse(
            figure_id=figure.id, status=FigureRenderStatus.PENDING, assets=[]
        )

    async def _prepare_render(self, figure: Figure) -> _PreparedRender:
        spec = FigureSpecModel.model_validate(figure.spec_json)
        series_data: list[list[Point]] = []
        labels: list[str | None] = []
        run_ids: list[uuid.UUID] = []
        total_points = 0
        for series in spec.series:
            source = series.source
            if isinstance(source, InlineSource):
                points = [(float(x), float(y)) for x, y in source.points]
                label = series.label
            else:
                run = await self._source_run(figure.project_id, source)
                label = series.label or source.metric_name
                if run is None:
                    points = []
                else:
                    if run.id not in run_ids:
                        run_ids.append(run.id)
                    rows = await self.metrics.series(run.id, source.metric_name)
                    points = [(float(s), v) for s, v in dedupe_points(rows)]
            total_points += len(points)
            if series.smoothing_window > 1:
                points = _smooth(points, series.smoothing_window)
            series_data.append(_downsample(points, MAX_RENDER_POINTS_PER_SERIES))
            labels.append(label)
        preset = await self._resolve_style(figure, spec)
        opts = {
            "title": spec.title,
            "x_label": spec.x_label,
            "y_label": spec.y_label,
            "legend": spec.legend,
            "y_scale": spec.y_scale,
        }
        return _PreparedRender(
            spec=spec,
            series_data=series_data,
            labels=labels,
            run_ids=run_ids,
            total_points=total_points,
            preset=preset,
            opts=opts,
        )

    async def _source_run(
        self, project_id: uuid.UUID, source: RunMetricSource
    ) -> ExperimentRun | None:
        if source.run_id is not None:
            run = await self.runs.get(project_id, source.run_id)
            if run is None:
                raise NotFoundError("Run not found.")
            return run
        assert source.experiment_id is not None  # enforced by the spec model
        exp = await self.experiments.get(project_id, source.experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        return await self.runs.latest_completed(source.experiment_id)

    async def _resolve_style(self, figure: Figure, spec: FigureSpecModel) -> StylePreset:
        slug = spec.style_slug
        if slug is None:
            from researchos.preferences.service import PreferenceService

            slug = await PreferenceService(self.db).figure_style_for_user(
                figure.created_by, figure.project_id
            )
        if slug not in PRESETS:
            logger.warning(
                "unknown_style_slug",
                figure_id=str(figure.id),
                slug=slug,
                fallback=DEFAULT_STYLE_SLUG,
            )
            slug = DEFAULT_STYLE_SLUG
        return PRESETS[slug]

    async def _execute_render(
        self, figure: Figure, prepared: _PreparedRender, *, timeout: float | None
    ) -> list[RenderedAssetInfo]:
        # Plain-value copies survive the rollback in the failure path (rollback
        # expires ORM attributes, which must not be lazily loaded afterwards).
        figure_id = figure.id
        project_id = figure.project_id
        figure_name = figure.name
        try:
            coro = asyncio.to_thread(
                render_figure_bytes,
                prepared.spec.chart,
                prepared.series_data,
                prepared.labels,
                prepared.opts,
                prepared.preset,
            )
            if timeout is not None:
                try:
                    rendered = await asyncio.wait_for(coro, timeout=timeout)
                except TimeoutError as exc:
                    raise DependencyError(
                        "Figure render timed out.", code="render_timeout"
                    ) from exc
            else:
                rendered = await coro
            now = datetime.now(tz=UTC)
            assets: list[RenderedAssetInfo] = []
            for fmt in ("svg", "png"):
                content = rendered[fmt]
                if len(content) > MAX_ASSET_BYTES:
                    raise ValidationError("Rendered asset exceeds the 4 MB cap.")
                sha = sha256_hex(content)
                await self.assets.upsert(
                    figure.id,
                    fmt,
                    content=content,
                    sha256=sha,
                    size_bytes=len(content),
                    rendered_at=now,
                )
                assets.append(
                    RenderedAssetInfo(format=fmt, size_bytes=len(content), sha256=sha)
                )
            figure.rendered_style_slug = prepared.preset.slug
            figure.rendered_style_version = prepared.preset.version
            figure.last_rendered_at = now
            figure.source_run_ids = [str(rid) for rid in prepared.run_ids]
            figure.status = FigureRenderStatus.RENDERED
            figure.stale = False
            figure.last_error = None
            await self._link_artifacts(figure, prepared.run_ids)
            await self.db.commit()
            return assets
        except Exception as exc:
            await self.db.rollback()
            figure.status = FigureRenderStatus.FAILED
            figure.last_error = str(exc)[:2000]
            await self.db.commit()
            await publish_figure_event(
                event_type="figure.render.failed",
                project_id=project_id,
                figure_id=figure_id,
                payload={"figure_id": str(figure_id), "name": figure_name, "error": str(exc)[:500]},
            )
            raise

    async def _publish_completed(self, figure: Figure, prepared: _PreparedRender) -> None:
        await publish_figure_event(
            event_type="figure.render.completed",
            project_id=figure.project_id,
            figure_id=figure.id,
            payload={
                "figure_id": str(figure.id),
                "name": figure.name,
                "formats": ["svg", "png"],
                "style_slug": prepared.preset.slug,
                "style_version": prepared.preset.version,
                "source_run_ids": [str(rid) for rid in prepared.run_ids],
            },
        )

    async def _link_artifacts(self, figure: Figure, run_ids: list[uuid.UUID]) -> None:
        """Upsert one ``figure`` artifact per distinct source run."""

        for run_id in run_ids:
            existing_list = await self.artifacts.list_for_run(run_id)
            existing = next(
                (
                    a
                    for a in existing_list
                    if (a.metadata_json or {}).get("figure_id") == str(figure.id)
                ),
                None,
            )
            name = f"{figure.name}.svg"
            uri = f"/projects/{figure.project_id}/figures/{figure.id}/assets/svg"
            metadata = {"figure_id": str(figure.id), "formats": ["svg", "png"]}
            if existing is None:
                self.db.add(
                    ExperimentArtifact(
                        run_id=run_id,
                        project_id=figure.project_id,
                        artifact_type="figure",
                        name=name,
                        uri=uri,
                        metadata_json=metadata,
                    )
                )
            else:
                existing.artifact_type = "figure"
                existing.name = name
                existing.uri = uri
                existing.metadata_json = metadata
        await self.db.flush()

    # --- assets --------------------------------------------------------------
    async def get_asset(
        self, actor: User, project_id: uuid.UUID, figure_id: uuid.UUID, fmt: str
    ) -> FigureAsset:
        figure = await self.get_figure(actor, project_id, figure_id)
        asset = await self.assets.get(figure.id, fmt)
        if asset is None:
            raise NotFoundError("Figure asset not found.")
        return asset

    # --- run-completion hook (internal; same transaction, no commit) ---------
    async def mark_stale_for_run(self, run: ExperimentRun) -> list[uuid.UUID]:
        """Flag figures affected by ``run`` completing. Returns flagged ids."""

        if run.status != ExperimentRunStatus.COMPLETED:
            return []
        flagged: list[uuid.UUID] = []
        pinned_run_cache: dict[uuid.UUID, ExperimentRun | None] = {}
        for figure in await self.figures.list_by_project(run.project_id):
            if figure.stale:
                continue
            try:
                spec = FigureSpecModel.model_validate(figure.spec_json)
            except Exception:  # tolerate legacy/invalid stored specs
                continue
            if await self._references_run(spec, run, pinned_run_cache):
                figure.stale = True
                flagged.append(figure.id)
        return flagged

    async def _references_run(
        self,
        spec: FigureSpecModel,
        run: ExperimentRun,
        pinned_run_cache: dict[uuid.UUID, ExperimentRun | None],
    ) -> bool:
        for series in spec.series:
            source = series.source
            if not isinstance(source, RunMetricSource):
                continue
            if source.run_id is None:
                if source.experiment_id == run.experiment_id:
                    return True
                continue
            if source.run_id == run.id:
                continue  # the completed run itself is not "newer" than itself
            if source.run_id not in pinned_run_cache:
                pinned_run_cache[source.run_id] = await self.db.get(
                    ExperimentRun, source.run_id
                )
            pinned = pinned_run_cache[source.run_id]
            if pinned is not None and pinned.experiment_id == run.experiment_id:
                return True
        return False


def _is_broker_error(exc: Exception) -> bool:
    try:
        from kombu.exceptions import OperationalError as KombuOperationalError
    except ImportError:  # pragma: no cover
        KombuOperationalError = ()
    return isinstance(exc, (KombuOperationalError, ConnectionError, OSError))


def _smooth(points: list[Point], window: int) -> list[Point]:
    """Centered rolling mean over the value axis."""

    if window <= 1 or len(points) <= 1:
        return points
    half = window // 2
    out: list[Point] = []
    for i in range(len(points)):
        lo = max(0, i - half)
        hi = min(len(points), i + half + 1)
        out.append((points[i][0], fmean(v for _, v in points[lo:hi])))
    return out


def _downsample(points: list[Point], cap: int) -> list[Point]:
    """Uniform stride downsample to <= cap points, keeping the last point."""

    if len(points) <= cap:
        return points
    stride = math.ceil(len(points) / cap)
    sampled = points[::stride]
    if sampled[-1] != points[-1]:
        sampled[-1] = points[-1]
    return sampled
