"""Coding chat business logic and authorization.

``post_message`` persists the user turn, then spawns a coding agent run whose
context carries ``chat_session_id`` — the agent injects prior turns into its
prompt and its finalize persists the assistant reply, so the pane can be
rebuilt entirely from REST while streaming rides the ``agent.run.*`` events.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.service import AgentRunService
from researchos.common.errors import AppError, NotFoundError
from researchos.common.pagination import Page
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .models import ChatMessage, ChatSession


class SessionBusyError(AppError):
    code = "session_busy"
    http_status = 409
    message = "The session's latest run is still in progress."


class CodingChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def create_session(
        self, actor: User, project_id: uuid.UUID, *, title: str = ""
    ) -> ChatSession:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        session = ChatSession(
            project_id=project_id,
            created_by=actor.id,
            agent_type=AgentType.CODING,
            title=title[:200],
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_sessions(
        self, actor: User, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[ChatSession]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        total = await self.db.scalar(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.project_id == project_id)
        )
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.project_id == project_id)
            .order_by(ChatSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return Page(
            items=list(result.scalars().all()), total=int(total or 0), limit=limit, offset=offset
        )

    async def get_session(
        self, actor: User, project_id: uuid.UUID, session_id: uuid.UUID
    ) -> ChatSession:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.project_id == project_id)
            .options(selectinload(ChatSession.messages))
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("Chat session not found.")
        return session

    async def _next_seq(self, session_id: uuid.UUID) -> int:
        current = await self.db.scalar(
            select(func.max(ChatMessage.seq)).where(ChatMessage.session_id == session_id)
        )
        return int(current) + 1 if current is not None else 0

    async def _latest_run_busy(self, session_id: uuid.UUID) -> bool:
        """Whether the session's newest linked run is still queued/running."""

        latest_run_id = await self.db.scalar(
            select(ChatMessage.agent_run_id)
            .where(ChatMessage.session_id == session_id, ChatMessage.agent_run_id.is_not(None))
            .order_by(ChatMessage.seq.desc())
            .limit(1)
        )
        if latest_run_id is None:
            return False
        run = await self.db.get(AgentRun, latest_run_id)
        return run is not None and run.status in (AgentRunStatus.QUEUED, AgentRunStatus.RUNNING)

    async def _insert_message(
        self,
        session: ChatSession,
        *,
        role: str,
        content: str,
    ) -> ChatMessage:
        """Insert with one retry on seq collision (unique constraint safety net)."""

        session_id = session.id
        for attempt in (0, 1):
            seq = await self._next_seq(session_id)
            message = ChatMessage(session_id=session_id, seq=seq, role=role, content=content)
            self.db.add(message)
            try:
                await self.db.flush()
            except IntegrityError:
                await self.db.rollback()
                if attempt == 1:
                    raise
                continue
            if seq == 0 and role == "user" and not session.title:
                session.title = content[:200]
            return message
        raise RuntimeError("unreachable")  # pragma: no cover

    async def post_message(
        self, actor: User, project_id: uuid.UUID, session_id: uuid.UUID, *, message: str
    ) -> tuple[ChatMessage, AgentRun]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        session = await self.get_session(actor, project_id, session_id)
        if await self._latest_run_busy(session.id):
            raise SessionBusyError()

        user_message = await self._insert_message(session, role="user", content=message)
        await self.db.commit()

        run = await AgentRunService(self.db).create_run(
            actor,
            project_id,
            agent_type=AgentType.CODING,
            message=message,
            context={"chat_session_id": str(session_id)},
        )
        user_message.agent_run_id = run.id
        await self.db.commit()
        return user_message, run
