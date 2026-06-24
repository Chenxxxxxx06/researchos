"""Agents data access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AgentRun, AgentRunEvent, ToolCall


class AgentRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, run: AgentRun) -> AgentRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_by_id(self, project_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun | None:
        run = await self.db.get(AgentRun, run_id)
        if run is None or run.project_id != project_id:
            return None
        return run

    async def get_unscoped(self, run_id: uuid.UUID) -> AgentRun | None:
        return await self.db.get(AgentRun, run_id)

    async def list_by_project(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[AgentRun], int]:
        total = await self.db.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.project_id == project_id)
        )
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.project_id == project_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)


class ToolCallRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_seq(self, agent_run_id: uuid.UUID) -> int:
        current = await self.db.scalar(
            select(func.count()).select_from(ToolCall).where(ToolCall.agent_run_id == agent_run_id)
        )
        return int(current or 0)

    async def create(self, tool_call: ToolCall) -> ToolCall:
        self.db.add(tool_call)
        await self.db.flush()
        return tool_call

    async def list_by_run(self, agent_run_id: uuid.UUID) -> list[ToolCall]:
        result = await self.db.execute(
            select(ToolCall).where(ToolCall.agent_run_id == agent_run_id).order_by(ToolCall.seq)
        )
        return list(result.scalars().all())


class AgentRunEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_seq(self, agent_run_id: uuid.UUID) -> int:
        current = await self.db.scalar(
            select(func.max(AgentRunEvent.seq)).where(AgentRunEvent.agent_run_id == agent_run_id)
        )
        return int(current) + 1 if current is not None else 0

    async def append(
        self,
        *,
        agent_run_id: uuid.UUID,
        project_id: uuid.UUID,
        seq: int,
        event_type: str,
        payload: dict,
    ) -> AgentRunEvent:
        event = AgentRunEvent(
            agent_run_id=agent_run_id,
            project_id=project_id,
            seq=seq,
            event_type=event_type,
            payload_json=payload,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_after(self, agent_run_id: uuid.UUID, *, after_seq: int) -> list[AgentRunEvent]:
        result = await self.db.execute(
            select(AgentRunEvent)
            .where(
                AgentRunEvent.agent_run_id == agent_run_id,
                AgentRunEvent.seq > after_seq,
            )
            .order_by(AgentRunEvent.seq)
        )
        return list(result.scalars().all())
