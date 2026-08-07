"""Research Mission persistence helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import MissionStatus, MissionStepKind
from .models import MissionEvent, MissionStep, ResearchMission


class MissionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, project_id: uuid.UUID, mission_id: uuid.UUID) -> ResearchMission | None:
        mission = await self.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != project_id:
            return None
        return mission

    async def list_missions(
        self,
        project_id: uuid.UUID,
        *,
        status: MissionStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ResearchMission], int]:
        where = [ResearchMission.project_id == project_id]
        if status is not None:
            where.append(ResearchMission.status == status)
        total = await self.db.scalar(
            select(func.count()).select_from(ResearchMission).where(*where)
        )
        result = await self.db.execute(
            select(ResearchMission)
            .where(*where)
            .order_by(ResearchMission.last_activity_at.desc(), ResearchMission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def steps(self, mission_id: uuid.UUID) -> list[MissionStep]:
        result = await self.db.execute(
            select(MissionStep)
            .where(MissionStep.mission_id == mission_id)
            .order_by(MissionStep.position.asc())
        )
        return list(result.scalars().all())

    async def step(
        self, mission_id: uuid.UUID, step_kind: MissionStepKind
    ) -> MissionStep | None:
        return await self.db.scalar(
            select(MissionStep).where(
                MissionStep.mission_id == mission_id,
                MissionStep.step_kind == step_kind,
            )
        )

    async def events(
        self, mission_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[MissionEvent], int]:
        total = await self.db.scalar(
            select(func.count()).select_from(MissionEvent).where(
                MissionEvent.mission_id == mission_id
            )
        )
        result = await self.db.execute(
            select(MissionEvent)
            .where(MissionEvent.mission_id == mission_id)
            .order_by(MissionEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)
