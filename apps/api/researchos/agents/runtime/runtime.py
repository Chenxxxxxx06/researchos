"""Agent runtime orchestration.

Drives the LLM/tool loop for a single AgentRun, persists state and events, and
enforces cancellation and citation integrity. Invoked by the Celery
``agents.run_agent`` task (and directly by tests).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.cancellation import is_cancel_requested
from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.llm import LLMMessage, LLMProvider, LLMTool, get_llm_provider
from researchos.agents.llm.base import StreamDone, TextDelta, ToolCall, Usage
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.common.config import get_settings
from researchos.common.db import get_sessionmaker
from researchos.identity.repository import UserRepository

from .base import Agent, AgentContext
from .coding_agent import CodingAgent
from .critic_agent import CriticAgent
from .events import EventEmitter
from .experiment_agent import ExperimentAgent
from .latex_agent import LatexAgent
from .research_agent import ResearchAgent
from .tools import TOOL_REGISTRY, ToolBroker, ToolContext

logger = structlog.get_logger(__name__)

_AGENTS: dict[AgentType, type[Agent]] = {
    AgentType.RESEARCH: ResearchAgent,
    AgentType.CRITIC: CriticAgent,
    AgentType.CODING: CodingAgent,
    AgentType.EXPERIMENT: ExperimentAgent,
    AgentType.LATEX: LatexAgent,
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


class AgentRuntime:
    def __init__(
        self,
        db: AsyncSession,
        *,
        llm: LLMProvider | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.db = db
        self.llm = llm or get_llm_provider()
        self.http_client = http_client
        self.settings = get_settings()

    async def run(self, run_id: uuid.UUID) -> AgentRun | None:
        runs = AgentRunRepository(self.db)
        run = await runs.get_unscoped(run_id)
        if run is None:
            logger.warning("agent_run_missing", run_id=str(run_id))
            return None

        emitter = EventEmitter(self.db, project_id=run.project_id, run_id=run.id)

        if await is_cancel_requested(run.id) or run.status == AgentRunStatus.CANCELLED:
            await self._finalize_cancelled(run, emitter)
            return run

        actor = await UserRepository(self.db).get_by_id(run.user_id)
        if actor is None:
            await self._finalize_failed(run, emitter, "Triggering user not found.")
            return run

        run.status = AgentRunStatus.RUNNING
        run.started_at = _now()
        await self.db.commit()
        await emitter.started(run.agent_type.value)

        agent = _AGENTS[run.agent_type]()
        tool_ctx = ToolContext(
            db=self.db,
            actor=actor,
            project_id=run.project_id,
            run_id=run.id,
            emitter=emitter,
            allowed_tools=set(agent.allowed_tools),
            http_client=self.http_client,
        )
        broker = ToolBroker(tool_ctx)
        actx = AgentContext(
            db=self.db,
            actor=actor,
            project_id=run.project_id,
            run=run,
            message=run.input_json.get("message", ""),
            context=run.input_json.get("context", {}),
            tool_ctx=tool_ctx,
        )

        try:
            output_text, usage = await self._run_loop(agent, actx, tool_ctx, broker, emitter)
        except Exception as exc:  # noqa: BLE001 - persist and report any failure
            logger.exception("agent_run_failed", run_id=str(run.id))
            await self._finalize_failed(run, emitter, str(exc))
            return run

        if await is_cancel_requested(run.id):
            await self._finalize_cancelled(run, emitter)
            return run

        output_json, citations = await agent.finalize(
            actx,
            output_text=output_text,
            whitelist=tool_ctx.citation_whitelist,
            citation_sources=tool_ctx.citation_sources,
            usage=usage,
        )
        run.output_json = output_json
        run.token_usage_json = usage
        run.status = AgentRunStatus.COMPLETED
        run.finished_at = _now()
        await self.db.commit()

        summary = output_json.get("message") or output_json.get("novelty_summary") or ""
        await emitter.completed(summary, citations, usage)
        return run

    async def _run_loop(
        self,
        agent: Agent,
        actx: AgentContext,
        tool_ctx: ToolContext,
        broker: ToolBroker,
        emitter: EventEmitter,
    ) -> tuple[str, dict]:
        messages = await agent.build_messages(actx)
        llm_tools = [
            LLMTool(
                name=TOOL_REGISTRY[t].name,
                description=TOOL_REGISTRY[t].description,
                parameters=TOOL_REGISTRY[t].parameters,
            )
            for t in agent.allowed_tools
            if t in TOOL_REGISTRY
        ]

        text_buffer = ""
        usage: dict = {}
        tool_count = 0

        while True:
            requested: list[ToolCall] = []
            async for event in self.llm.stream(
                messages=messages, tools=llm_tools, response_schema=agent.response_schema
            ):
                if isinstance(event, TextDelta):
                    text_buffer += event.text
                    await emitter.token(event.text)
                elif isinstance(event, ToolCall):
                    requested.append(event)
                elif isinstance(event, Usage):
                    usage = {
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                    }
                elif isinstance(event, StreamDone):
                    pass

            if requested and tool_count < self.settings.agent_max_tool_calls:
                for call in requested:
                    result = await broker.execute(call.name, call.arguments)
                    messages.append(LLMMessage(role="assistant", content=""))
                    messages.append(
                        LLMMessage(
                            role="tool",
                            name=call.name,
                            tool_call_id=call.id,
                            content=json.dumps(result),
                        )
                    )
                    tool_count += 1
                continue
            return text_buffer, usage

    async def _finalize_failed(self, run: AgentRun, emitter: EventEmitter, error: str) -> None:
        run.status = AgentRunStatus.FAILED
        run.error_json = {"message": error}
        run.finished_at = _now()
        await self.db.commit()
        await emitter.failed(error)

    async def _finalize_cancelled(self, run: AgentRun, emitter: EventEmitter) -> None:
        run.status = AgentRunStatus.CANCELLED
        run.finished_at = _now()
        await self.db.commit()
        await emitter.cancelled()


async def run_agent_run(run_id: str, *, http_client: httpx.AsyncClient | None = None) -> None:
    """Entry point used by the Celery task: opens a session and runs the agent."""

    async with get_sessionmaker()() as db:
        await AgentRuntime(db, http_client=http_client).run(uuid.UUID(run_id))
