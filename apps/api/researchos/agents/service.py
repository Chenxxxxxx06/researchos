"""Agent run business logic and authorization.

The service creates persisted AgentRun records and dispatches execution to the
Celery ``agents`` queue. Agent logic itself lives in the runtime layer, never in
routes or this service.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.celery_app import dispatch_agent_run
from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.pagination import Page
from researchos.common.rate_limit import enforce_rate_limit
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .cancellation import request_cancel
from .enums import AgentRunStatus, AgentType
from .models import AgentRun, AgentRunEvent
from .repository import AgentRunEventRepository, AgentRunRepository


class AgentRunService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.runs = AgentRunRepository(db)
        self.events = AgentRunEventRepository(db)
        self.projects = ProjectService(db)

    async def create_run(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        agent_type: AgentType,
        message: str,
        context: dict | None = None,
    ) -> AgentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        settings = get_settings()
        await enforce_rate_limit(
            f"agent_run:{actor.id}",
            limit=settings.rate_limit_agent_runs_per_minute,
        )

        context = context or {}
        if agent_type == AgentType.CRITIC and not context.get("idea_id"):
            raise ValidationError("Critic runs require context.idea_id.")

        run = await self.runs.create(
            AgentRun(
                project_id=project_id,
                user_id=actor.id,
                agent_type=agent_type,
                status=AgentRunStatus.QUEUED,
                input_json={"message": message, "context": context},
            )
        )
        await self.db.commit()
        # Dispatch only after the row is durable.
        dispatch_agent_run(str(run.id))
        return run

    async def list_runs(
        self, actor: User, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[AgentRun]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        items, total = await self.runs.list_by_project(project_id, limit=limit, offset=offset)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get_run(self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        run = await self.runs.get_by_id(project_id, run_id)
        if run is None:
            raise NotFoundError("Agent run not found.")
        return run

    async def get_events(
        self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID, *, after_seq: int
    ) -> list[AgentRunEvent]:
        run = await self.get_run(actor, project_id, run_id)
        return await self.events.list_after(run.id, after_seq=after_seq)

    async def cancel_run(self, actor: User, project_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        run = await self.runs.get_by_id(project_id, run_id)
        if run is None:
            raise NotFoundError("Agent run not found.")
        if run.status.is_terminal:
            return run
        await request_cancel(run.id)
        # If it has not started yet, mark cancelled immediately; a running task
        # will observe the flag cooperatively and finalize itself.
        if run.status == AgentRunStatus.QUEUED:
            run.status = AgentRunStatus.CANCELLED
            await self.db.commit()
            await self.db.refresh(run)
        return run
