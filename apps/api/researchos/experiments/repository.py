"""Experiment data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import ExperimentRunStatus
from .models import (
    Experiment,
    ExperimentArtifact,
    ExperimentIngestToken,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)


class ExperimentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, experiment: Experiment) -> Experiment:
        self.db.add(experiment)
        await self.db.flush()
        return experiment

    async def get(self, project_id: uuid.UUID, experiment_id: uuid.UUID) -> Experiment | None:
        exp = await self.db.get(Experiment, experiment_id)
        return exp if exp and exp.project_id == project_id else None

    async def list(self, project_id: uuid.UUID) -> list[Experiment]:
        result = await self.db.execute(
            select(Experiment)
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(result.scalars().all())


class RunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, run: ExperimentRun) -> ExperimentRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get(self, project_id: uuid.UUID, run_id: uuid.UUID) -> ExperimentRun | None:
        run = await self.db.get(ExperimentRun, run_id)
        return run if run and run.project_id == project_id else None

    async def list_for_experiment(self, experiment_id: uuid.UUID) -> list[ExperimentRun]:
        result = await self.db.execute(
            select(ExperimentRun)
            .where(ExperimentRun.experiment_id == experiment_id)
            .order_by(ExperimentRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_project(self, project_id: uuid.UUID) -> list[ExperimentRun]:
        result = await self.db.execute(
            select(ExperimentRun)
            .where(ExperimentRun.project_id == project_id)
            .order_by(ExperimentRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def latest_completed(self, experiment_id: uuid.UUID) -> ExperimentRun | None:
        return await self.db.scalar(
            select(ExperimentRun)
            .where(
                ExperimentRun.experiment_id == experiment_id,
                ExperimentRun.status == ExperimentRunStatus.COMPLETED,
            )
            .order_by(
                ExperimentRun.finished_at.desc().nulls_last(),
                ExperimentRun.created_at.desc(),
            )
            .limit(1)
        )

    async def allocate_log_seqs(self, run_id: uuid.UUID, n: int) -> int:
        """Atomically reserve ``n`` log seqs; returns the first seq of the block."""

        result = await self.db.execute(
            update(ExperimentRun)
            .where(ExperimentRun.id == run_id)
            .values(log_next_seq=ExperimentRun.log_next_seq + n)
            .returning(ExperimentRun.log_next_seq)
        )
        end = result.scalar_one()
        return int(end) - n


class MetricRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, metric: ExperimentMetric) -> None:
        self.db.add(metric)

    def bulk_add(self, metrics: list[ExperimentMetric]) -> None:
        self.db.add_all(metrics)

    async def list_for_run(self, run_id: uuid.UUID) -> list[ExperimentMetric]:
        result = await self.db.execute(
            select(ExperimentMetric)
            .where(ExperimentMetric.run_id == run_id)
            .order_by(ExperimentMetric.name, ExperimentMetric.step)
        )
        return list(result.scalars().all())

    async def series(self, run_id: uuid.UUID, name: str) -> list[ExperimentMetric]:
        result = await self.db.execute(
            select(ExperimentMetric)
            .where(ExperimentMetric.run_id == run_id, ExperimentMetric.name == name)
            .order_by(ExperimentMetric.step)
        )
        return list(result.scalars().all())


class LogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, log: ExperimentLog) -> None:
        self.db.add(log)

    async def list_for_run(self, run_id: uuid.UUID) -> list[ExperimentLog]:
        result = await self.db.execute(
            select(ExperimentLog).where(ExperimentLog.run_id == run_id).order_by(ExperimentLog.seq)
        )
        return list(result.scalars().all())


class ArtifactRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, artifact: ExperimentArtifact) -> ExperimentArtifact:
        self.db.add(artifact)
        await self.db.flush()
        return artifact

    async def list_for_run(self, run_id: uuid.UUID) -> list[ExperimentArtifact]:
        result = await self.db.execute(
            select(ExperimentArtifact)
            .where(ExperimentArtifact.run_id == run_id)
            .order_by(ExperimentArtifact.created_at.desc())
        )
        return list(result.scalars().all())


class IngestTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, token: ExperimentIngestToken) -> ExperimentIngestToken:
        self.db.add(token)
        await self.db.flush()
        return token

    async def get(
        self, project_id: uuid.UUID, token_id: uuid.UUID
    ) -> ExperimentIngestToken | None:
        token = await self.db.get(ExperimentIngestToken, token_id)
        return token if token and token.project_id == project_id else None

    async def get_active_by_hash(self, token_hash: str) -> ExperimentIngestToken | None:
        return await self.db.scalar(
            select(ExperimentIngestToken).where(
                ExperimentIngestToken.token_hash == token_hash,
                ExperimentIngestToken.revoked_at.is_(None),
            )
        )

    async def list_for_project(self, project_id: uuid.UUID) -> list[ExperimentIngestToken]:
        result = await self.db.execute(
            select(ExperimentIngestToken)
            .where(ExperimentIngestToken.project_id == project_id)
            .order_by(ExperimentIngestToken.created_at.desc())
        )
        return list(result.scalars().all())
