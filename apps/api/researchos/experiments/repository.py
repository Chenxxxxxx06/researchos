"""Experiment data access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Experiment,
    ExperimentArtifact,
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


class MetricRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, metric: ExperimentMetric) -> None:
        self.db.add(metric)

    async def list_for_run(self, run_id: uuid.UUID) -> list[ExperimentMetric]:
        result = await self.db.execute(
            select(ExperimentMetric)
            .where(ExperimentMetric.run_id == run_id)
            .order_by(ExperimentMetric.name, ExperimentMetric.step)
        )
        return list(result.scalars().all())


class LogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_seq(self, run_id: uuid.UUID) -> int:
        current = await self.db.scalar(
            select(func.count()).select_from(ExperimentLog).where(ExperimentLog.run_id == run_id)
        )
        return int(current or 0)

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
