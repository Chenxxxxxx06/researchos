"""Agent run event emitter.

Publishes typed envelopes to the project's Redis channel for live WebSocket
fan-out, and persists *coarse* events (started / tool_call / completed / failed /
cancelled) to ``agent_run_events`` for REST fallback and reconnection. Token
events are published live only and are intentionally not persisted; their
payload carries a monotone per-run ``seq`` so the frontend can order deltas.

Event persistence is decoupled from the run: a seq collision retries once
against a re-seeded allocator; a second failure is logged and swallowed — a
lost persisted event must never fail the run (the live publish still goes out).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.repository import AgentRunEventRepository
from researchos.common.pubsub import publish_event
from researchos.websocket.envelopes import build_agent_event

logger = structlog.get_logger(__name__)


class EventEmitter:
    def __init__(self, db: AsyncSession, *, project_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self.db = db
        self.project_id = project_id
        self.run_id = run_id
        self.events = AgentRunEventRepository(db)
        self._token_seq = 0

    async def _persist(self, event_type: str, payload: dict) -> None:
        try:
            seq = await self.events.next_seq(self.run_id)
            await self.events.append(
                agent_run_id=self.run_id,
                project_id=self.project_id,
                seq=seq,
                event_type=event_type,
                payload=payload,
            )
            await self.db.commit()
            return
        except IntegrityError:
            await self.db.rollback()
            self.events.reset_seq_cache(self.run_id)
        try:
            seq = await self.events.next_seq(self.run_id)
            await self.events.append(
                agent_run_id=self.run_id,
                project_id=self.project_id,
                seq=seq,
                event_type=event_type,
                payload=payload,
            )
            await self.db.commit()
        except Exception:  # noqa: BLE001 - persistence must never fail the run
            logger.warning(
                "event_persist_failed",
                run_id=str(self.run_id),
                event_type=event_type,
            )
            await self.db.rollback()

    async def emit(self, event_type: str, payload: dict, *, persist: bool) -> None:
        envelope = build_agent_event(
            event_type=event_type,
            project_id=self.project_id,
            agent_run_id=self.run_id,
            payload=payload,
        )
        if persist:
            await self._persist(event_type, payload)
        await publish_event(str(self.project_id), envelope)

    # --- convenience helpers -------------------------------------------------
    async def started(self, agent_type: str, skills: list[dict] | None = None) -> None:
        await self.emit(
            "agent.run.started",
            {"agent_type": agent_type, "skills": skills or []},
            persist=True,
        )

    async def token(self, delta: str) -> None:
        seq = self._token_seq
        self._token_seq += 1
        await self.emit("agent.run.token", {"delta": delta, "seq": seq}, persist=False)

    async def tool_call_started(self, seq: int, tool_name: str, arguments: dict) -> None:
        await self.emit(
            "agent.run.tool_call.started",
            {"seq": seq, "tool_name": tool_name, "arguments": arguments},
            persist=True,
        )

    async def tool_call_completed(
        self, seq: int, tool_name: str, status: str, result_summary: str | None = None
    ) -> None:
        await self.emit(
            "agent.run.tool_call.completed",
            {
                "seq": seq,
                "tool_name": tool_name,
                "status": status,
                "result_summary": result_summary,
            },
            persist=True,
        )

    async def completed(self, output: str, citations: list[dict], usage: dict) -> None:
        await self.emit(
            "agent.run.completed",
            {"output": output, "citations": citations, "usage": usage},
            persist=True,
        )

    async def failed(self, error: str, code: str = "agent_error") -> None:
        await self.emit("agent.run.failed", {"error": error, "code": code}, persist=True)

    async def cancelled(self) -> None:
        await self.emit("agent.run.cancelled", {}, persist=True)
