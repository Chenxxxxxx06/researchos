"""Experiment business logic and authorization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .enums import ExperimentRunStatus
from .models import (
    Experiment,
    ExperimentArtifact,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)
from .repository import (
    ArtifactRepository,
    ExperimentRepository,
    LogRepository,
    MetricRepository,
    RunRepository,
)
from .schemas import CreateArtifactRequest, CreateRunRequest, MetricPoint


class ExperimentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.experiments = ExperimentRepository(db)
        self.runs = RunRepository(db)
        self.metrics = MetricRepository(db)
        self.logs = LogRepository(db)
        self.artifacts = ArtifactRepository(db)
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
        started = datetime.now(tz=UTC) if payload.status != ExperimentRunStatus.QUEUED else None
        finished = (
            datetime.now(tz=UTC)
            if payload.status in (ExperimentRunStatus.COMPLETED, ExperimentRunStatus.FAILED)
            else None
        )
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
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def list_runs(
        self, actor: User, project_id: uuid.UUID, experiment_id: uuid.UUID
    ) -> list[ExperimentRun]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
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

    async def update_run_status(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, status: ExperimentRunStatus
    ) -> ExperimentRun:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        run.status = status
        if status in (ExperimentRunStatus.COMPLETED, ExperimentRunStatus.FAILED):
            run.finished_at = datetime.now(tz=UTC)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    # --- metrics / logs / artifacts -----------------------------------------
    async def record_metrics(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, points: list[MetricPoint]
    ) -> int:
        run = await self.get_run(actor, project_id, run_id)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        for p in points:
            self.metrics.add(
                ExperimentMetric(
                    run_id=run.id, project_id=project_id, name=p.name, step=p.step, value=p.value
                )
            )
        await self.db.commit()
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
        seq = await self.logs.next_seq(run.id)
        log = ExperimentLog(
            run_id=run.id, project_id=project_id, seq=seq, level=level, message=message
        )
        self.logs.add(log)
        await self.db.commit()
        await self.db.refresh(log)
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
