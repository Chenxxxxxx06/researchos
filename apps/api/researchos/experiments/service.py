"""Experiment business logic and authorization."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError
from researchos.common.hashing import sha256_hex
from researchos.common.roles import ProjectRole
from researchos.figures.events import publish_anchor_values_updated, publish_run_event
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .enums import ALLOWED_TRANSITIONS, TERMINAL_STATUSES, ExperimentRunStatus
from .models import (
    Experiment,
    ExperimentArtifact,
    ExperimentIngestToken,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)
from .repository import (
    ArtifactRepository,
    ExperimentRepository,
    IngestTokenRepository,
    LogRepository,
    MetricRepository,
    RunRepository,
)
from .schemas import (
    CreateArtifactRequest,
    CreateRunRequest,
    MetricPoint,
    UpdateExperimentRequest,
)

INGEST_TOKEN_PREFIX = "rosit_"

_RUN_EVENT_TYPES: dict[ExperimentRunStatus, str] = {
    ExperimentRunStatus.QUEUED: "experiment.run.queued",
    ExperimentRunStatus.RUNNING: "experiment.run.started",
    ExperimentRunStatus.COMPLETED: "experiment.run.completed",
    ExperimentRunStatus.FAILED: "experiment.run.failed",
    ExperimentRunStatus.CANCELLED: "experiment.run.failed",
}


def generate_ingest_token() -> tuple[str, str, str]:
    """Return (plaintext, sha256 hash, display prefix) for a new ingest token."""

    plaintext = INGEST_TOKEN_PREFIX + secrets.token_hex(20)
    return plaintext, sha256_hex(plaintext), plaintext[:12]


class ExperimentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.experiments = ExperimentRepository(db)
        self.runs = RunRepository(db)
        self.metrics = MetricRepository(db)
        self.logs = LogRepository(db)
        self.artifacts = ArtifactRepository(db)
        self.ingest_tokens = IngestTokenRepository(db)
        self.projects = ProjectService(db)

    # --- experiments ---------------------------------------------------------
    async def create_experiment(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        goal: str | None,
    ) -> Experiment:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        exp = await self.experiments.add(
            Experiment(
                project_id=project_id,
                name=name,
                description=description,
                goal=goal,
                created_by=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(exp)
        return exp

    async def list_experiments(self, actor: User, project_id: uuid.UUID) -> list[Experiment]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.experiments.list(project_id)

    async def get_experiment(
        self, actor: User, project_id: uuid.UUID, experiment_id: uuid.UUID
    ) -> Experiment:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        exp = await self.experiments.get(project_id, experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        return exp

    async def update_experiment(
        self,
        actor: User,
        project_id: uuid.UUID,
        experiment_id: uuid.UUID,
        payload: UpdateExperimentRequest,
    ) -> Experiment:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        exp = await self.experiments.get(project_id, experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        fields = payload.model_fields_set
        if "name" in fields and payload.name is not None:
            exp.name = payload.name
        if "description" in fields:
            exp.description = payload.description
        if "goal" in fields:
            exp.goal = payload.goal
        if "metric_meta" in fields and payload.metric_meta is not None:
            exp.metric_meta_json = {
                name: entry.model_dump(exclude_none=True)
                for name, entry in payload.metric_meta.items()
            }
        await self.db.commit()
        await self.db.refresh(exp)
        return exp

    async def get_metric_meta_for_run(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict:
        """Metric metadata of the run's experiment (for the experiment agent)."""

        run = await self.get_run(actor, project_id, run_id)
        exp = await self.experiments.get(project_id, run.experiment_id)
        return dict(exp.metric_meta_json) if exp is not None else {}

    # --- runs ----------------------------------------------------------------
    async def create_run(
        self,
        actor: User,
        project_id: uuid.UUID,
        experiment_id: uuid.UUID,
        payload: CreateRunRequest,
    ) -> ExperimentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        exp = await self.experiments.get(project_id, experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        now = datetime.now(tz=UTC)
        started = now if payload.status != ExperimentRunStatus.QUEUED else None
        finished = now if payload.status in TERMINAL_STATUSES else None
        run = await self.runs.add(
            ExperimentRun(
                experiment_id=experiment_id,
                project_id=project_id,
                name=payload.name,
                status=payload.status,
                git_commit=payload.git_commit,
                command=payload.command,
                config_json=payload.config,
                started_at=started,
                finished_at=finished,
                created_by=actor.id,
            )
        )
        stale_anchor_ids: list[uuid.UUID] = []
        if payload.status in TERMINAL_STATUSES:
            # A run born terminal still moves "latest completed" for anchors/figures.
            stale_anchor_ids = await self._fire_terminal_hooks(run)
        await self.db.commit()
        await self.db.refresh(run)
        await self._publish_run_status(run)
        await self._publish_anchor_staleness(project_id, stale_anchor_ids)
        return run

    async def list_runs(
        self, actor: User, project_id: uuid.UUID, experiment_id: uuid.UUID
    ) -> list[ExperimentRun]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        # 404 when the experiment is not in this project (hides existence; IDOR fix).
        exp = await self.experiments.get(project_id, experiment_id)
        if exp is None:
            raise NotFoundError("Experiment not found.")
        return await self.runs.list_for_experiment(experiment_id)

    async def list_project_runs(self, actor: User, project_id: uuid.UUID) -> list[ExperimentRun]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.runs.list_for_project(project_id)

    async def get_run(self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID) -> ExperimentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        run = await self.runs.get(project_id, run_id)
        if run is None:
            raise NotFoundError("Run not found.")
        return run

    def _apply_status_transition(self, run: ExperimentRun, status: ExperimentRunStatus) -> bool:
        """Mutate ``run`` for a guarded transition; False = idempotent no-op.

        Raises ``ConflictError(code="invalid_transition")`` on an illegal move.
        No commit — the caller owns the transaction.
        """

        if run.status == status:
            return False
        if status not in ALLOWED_TRANSITIONS.get(run.status, frozenset()):
            raise ConflictError(
                f"Cannot move run from {run.status.value} to {status.value}.",
                code="invalid_transition",
            )
        now = datetime.now(tz=UTC)
        run.status = status
        if status == ExperimentRunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if status in TERMINAL_STATUSES:
            run.finished_at = now
        return True

    async def _fire_terminal_hooks(self, run: ExperimentRun) -> list[uuid.UUID]:
        """Anchor/figure staleness updates in the same transaction (no commit).

        Lazy imports avoid an import cycle (figures services import this module).
        """

        from researchos.figures.anchor_service import AnchorService
        from researchos.figures.figure_service import FigureService

        stale_anchor_ids = await AnchorService(self.db).mark_stale_for_experiment(
            run.experiment_id
        )
        await FigureService(self.db).mark_stale_for_run(run)
        return stale_anchor_ids

    async def _publish_run_status(self, run: ExperimentRun) -> None:
        await publish_run_event(
            event_type=_RUN_EVENT_TYPES[run.status],
            project_id=run.project_id,
            run_id=run.id,
            payload={
                "run_id": str(run.id),
                "experiment_id": str(run.experiment_id),
                "status": run.status.value,
            },
        )

    async def _publish_anchor_staleness(
        self, project_id: uuid.UUID, stale_anchor_ids: list[uuid.UUID]
    ) -> None:
        if not stale_anchor_ids:
            return
        await publish_anchor_values_updated(
            project_id=project_id,
            updated_count=0,
            stale_count=len(stale_anchor_ids),
            anchor_ids=[str(aid) for aid in stale_anchor_ids],
        )

    async def apply_run_status(
        self, run: ExperimentRun, status: ExperimentRunStatus
    ) -> list[uuid.UUID]:
        """Transition core shared by the PATCH route and the NDJSON ingest.

        Returns anchor ids flagged stale by the terminal hook (empty otherwise).
        """

        changed = self._apply_status_transition(run, status)
        if changed and status in TERMINAL_STATUSES:
            return await self._fire_terminal_hooks(run)
        return []

    async def update_run_status(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, status: ExperimentRunStatus
    ) -> ExperimentRun:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        if run.status == status:
            return run  # idempotent no-op
        stale_anchor_ids = await self.apply_run_status(run, status)
        await self.db.commit()
        await self.db.refresh(run)
        await self._publish_run_status(run)
        await self._publish_anchor_staleness(project_id, stale_anchor_ids)
        return run

    # --- metrics / logs / artifacts -----------------------------------------
    async def record_metrics(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, points: list[MetricPoint]
    ) -> int:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        self.metrics.bulk_add(
            [
                ExperimentMetric(
                    run_id=run.id, project_id=project_id, name=p.name, step=p.step, value=p.value
                )
                for p in points
            ]
        )
        await self.db.commit()
        await publish_run_event(
            event_type="experiment.metric.recorded",
            project_id=project_id,
            run_id=run.id,
            payload={
                "run_id": str(run.id),
                "count": len(points),
                "names": sorted({p.name for p in points}),
            },
        )
        return len(points)

    async def list_metrics(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[ExperimentMetric]:
        run = await self.get_run(actor, project_id, run_id)
        return await self.metrics.list_for_run(run.id)

    async def append_log(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, *, level: str, message: str
    ) -> ExperimentLog:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        seq = await self.runs.allocate_log_seqs(run.id, 1)
        log = ExperimentLog(
            run_id=run.id, project_id=project_id, seq=seq, level=level, message=message
        )
        self.logs.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        await publish_run_event(
            event_type="experiment.log.appended",
            project_id=project_id,
            run_id=run.id,
            payload={"run_id": str(run.id), "count": 1, "last_seq": seq},
        )
        return log

    async def list_logs(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[ExperimentLog]:
        run = await self.get_run(actor, project_id, run_id)
        return await self.logs.list_for_run(run.id)

    async def create_artifact(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, payload: CreateArtifactRequest
    ) -> ExperimentArtifact:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        artifact = await self.artifacts.add(
            ExperimentArtifact(
                run_id=run.id,
                project_id=project_id,
                name=payload.name,
                artifact_type=payload.artifact_type,
                uri=payload.uri,
                size_bytes=payload.size_bytes,
                metadata_json=payload.metadata,
            )
        )
        await self.db.commit()
        await self.db.refresh(artifact)
        return artifact

    async def list_artifacts(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[ExperimentArtifact]:
        run = await self.get_run(actor, project_id, run_id)
        return await self.artifacts.list_for_run(run.id)

    # --- ingest tokens --------------------------------------------------------
    async def create_ingest_token(
        self, actor: User, project_id: uuid.UUID, *, name: str
    ) -> tuple[ExperimentIngestToken, str]:
        """Issue a token; the plaintext is returned exactly once."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        plaintext, token_hash, prefix = generate_ingest_token()
        token = await self.ingest_tokens.add(
            ExperimentIngestToken(
                project_id=project_id,
                name=name,
                token_hash=token_hash,
                token_prefix=prefix,
                created_by=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(token)
        return token, plaintext

    async def list_ingest_tokens(
        self, actor: User, project_id: uuid.UUID
    ) -> list[ExperimentIngestToken]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        return await self.ingest_tokens.list_for_project(project_id)

    async def revoke_ingest_token(
        self, actor: User, project_id: uuid.UUID, token_id: uuid.UUID
    ) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        token = await self.ingest_tokens.get(project_id, token_id)
        if token is None:
            raise NotFoundError("Ingest token not found.")
        if token.revoked_at is None:  # idempotent
            token.revoked_at = datetime.now(tz=UTC)
        await self.db.commit()
