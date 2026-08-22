"""Agent runtime orchestration.

Drives the LLM/tool loop for a single AgentRun, persists state and events, and
enforces cancellation, timeouts, structured output, and citation integrity.
Invoked by the Celery ``agents.run_agent`` task (and directly by tests).

Loop contract: each iteration streams one model turn. Text is buffered
*per-iteration* — the final answer is the LAST iteration's text only; earlier
prose lives inside prior assistant messages. Tool round-trips are recorded as
one assistant message carrying ``tool_calls`` followed by one ``role="tool"``
message per call (the shape both real APIs require).
"""

from __future__ import annotations

import asyncio
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
from researchos.agents.llm.structured import StructuredOutputError, _check_required, extract_json
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.common.config import get_settings
from researchos.common.db import get_sessionmaker
from researchos.common.errors import AppError
from researchos.identity.repository import UserRepository
from researchos.skills.service import RuntimeSkill

from .base import Agent, AgentContext
from .citation_organizer_agent import CitationOrganizerAgent
from .coding_agent import CodingAgent
from .critic_agent import CriticAgent
from .events import EventEmitter
from .experiment_agent import ExperimentAgent
from .experiment_planner_agent import ExperimentPlannerAgent
from .latex_agent import LatexAgent
from .program_agents import (
    BenchmarkAgent,
    DrawerAgent,
    IdeaExplorerAgent,
    LeaderAgent,
    ProgressAgent,
    ViewerAgent,
    WriterAgent,
)
from .reading_card_agent import ReadingCardAgent
from .research_agent import ResearchAgent
from .review_section_agent import ReviewSectionAgent
from .skills_injection import load_skills, skill_tool_grants
from .sql_analyst_agent import SqlAnalystAgent
from .tools import TOOL_REGISTRY, ToolBroker, ToolContext, ToolDenied

logger = structlog.get_logger(__name__)

_AGENTS: dict[AgentType, type[Agent]] = {
    AgentType.RESEARCH: ResearchAgent,
    AgentType.CRITIC: CriticAgent,
    AgentType.CODING: CodingAgent,
    AgentType.EXPERIMENT: ExperimentAgent,
    AgentType.EXPERIMENT_PLANNER: ExperimentPlannerAgent,
    AgentType.SQL_ANALYST: SqlAnalystAgent,
    AgentType.CITATION_ORGANIZER: CitationOrganizerAgent,
    AgentType.LATEX: LatexAgent,
    AgentType.READING_CARD: ReadingCardAgent,
    AgentType.REVIEW_SECTION: ReviewSectionAgent,
    AgentType.IDEA_EXPLORER: IdeaExplorerAgent,
    AgentType.BENCHMARK: BenchmarkAgent,
    AgentType.LEADER: LeaderAgent,
    AgentType.VIEWER: ViewerAgent,
    AgentType.WRITER: WriterAgent,
    AgentType.DRAWER: DrawerAgent,
    AgentType.PROGRESS: ProgressAgent,
}

_SYNTHESIS_NUDGE = (
    "You have used all available tool calls. Provide your final answer now "
    "using the information already gathered."
)


class AgentCancelledError(Exception):
    """Raised inside the loop when cooperative cancellation is requested."""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _effective_tools(agent: Agent, skills: list[RuntimeSkill]) -> set[str]:
    """Agent tools ∪ (skill grants ∩ platform allowlist ∩ live registry).

    Skill ``tool_permissions`` arrive pre-filtered against the manifest
    allowlist (service side); intersecting with ``TOOL_REGISTRY`` means
    declared-but-unregistered tools silently do not materialize.
    """

    granted: set[str] = set()
    for skill in skills:
        granted |= set(skill.tool_permissions)
    return set(agent.allowed_tools) | (granted & set(TOOL_REGISTRY))


class AgentRuntime:
    def __init__(
        self,
        db: AsyncSession,
        *,
        llm: LLMProvider | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.db = db
        self._llm = llm  # None means resolve from config in run()
        self.http_client = http_client
        self.settings = get_settings()

    async def run(self, run_id: uuid.UUID) -> AgentRun | None:
        runs = AgentRunRepository(self.db)
        run = await runs.get_unscoped(run_id)
        if run is None:
            logger.warning("agent_run_missing", run_id=str(run_id))
            return None

        # Resolve the LLM provider (lazy — uses project DB config if present).
        context = run.input_json.get("context", {})
        emitter = EventEmitter(self.db, project_id=run.project_id, run_id=run.id)
        selected_config_id = context.get("llm_config_id")
        try:
            # An injected provider remains authoritative for isolated runtime tests.
            llm = self._llm or await get_llm_provider(
                run.project_id,
                config_id=(
                    uuid.UUID(str(selected_config_id)) if selected_config_id is not None else None
                ),
            )
        except (AppError, ValueError) as exc:
            code = exc.code if isinstance(exc, AppError) else "validation_error"
            await self._finalize_failed(run, emitter, str(exc), code=code)
            return run

        if await is_cancel_requested(run.id) or run.status == AgentRunStatus.CANCELLED:
            await self._finalize_cancelled(run, emitter)
            return run

        actor = await UserRepository(self.db).get_by_id(run.user_id)
        if actor is None:
            await self._finalize_failed(run, emitter, "Triggering user not found.")
            return run

        requested_skills = context.get("skill_slugs")
        skills = await load_skills(
            self.db,
            run.project_id,
            run.agent_type,
            requested_slugs=requested_skills,
        )
        run.skill_ids_json = [{"slug": s.slug, "version": s.version} for s in skills]
        run.status = AgentRunStatus.RUNNING
        run.started_at = _now()
        await self.db.commit()
        await emitter.started(
            run.agent_type.value,
            [{"slug": s.slug, "version": s.version} for s in skills],
        )

        agent = _AGENTS[run.agent_type]()
        effective_tools = _effective_tools(agent, skills)
        grants = skill_tool_grants(skills)
        if grants:
            logger.info("skill_tool_grants", run_id=str(run.id), grants=grants)
        tool_ctx = ToolContext(
            db=self.db,
            actor=actor,
            project_id=run.project_id,
            run_id=run.id,
            emitter=emitter,
            allowed_tools=effective_tools,
            http_client=self.http_client,
        )
        if hasattr(tool_ctx, "granted_by"):
            # Populated once the tools partition adds the attribution field.
            tool_ctx.granted_by.update(grants)
        broker = ToolBroker(tool_ctx)
        actx = AgentContext(
            db=self.db,
            actor=actor,
            project_id=run.project_id,
            run=run,
            message=run.input_json.get("message", ""),
            context=context,
            tool_ctx=tool_ctx,
            skills=skills,
        )

        try:
            async with asyncio.timeout(float(self.settings.agent_run_timeout_seconds)):
                output_text, usage = await self._run_loop(
                    agent, actx, tool_ctx, broker, emitter, llm, effective_tools
                )
        except TimeoutError:
            run = await self._recover_session(run_id) or run
            await self._finalize_failed(run, emitter, "Agent run timed out.", code="timeout")
            return run
        except AgentCancelledError:
            run = await self._recover_session(run_id) or run
            await self._finalize_cancelled(run, emitter)
            return run
        except Exception as exc:  # noqa: BLE001 - persist and report any failure
            logger.exception("agent_run_failed", run_id=str(run_id))
            run = await self._recover_session(run_id) or run
            code = exc.code if isinstance(exc, AppError) else "agent_error"
            await self._finalize_failed(run, emitter, str(exc), code=code)
            return run

        if await is_cancel_requested(run.id):
            await self._finalize_cancelled(run, emitter)
            return run

        # Structured-output gate: a garbage answer FAILS the run visibly —
        # finalize is only ever handed normalized, valid JSON.
        if agent.response_schema is not None:
            try:
                parsed = extract_json(output_text)
                _check_required(parsed, agent.response_schema)
            except StructuredOutputError as exc:
                await self._finalize_failed(
                    run, emitter, str(exc), code="structured_output_parse_error"
                )
                return run
            output_text = json.dumps(parsed)

        output_json, citations = await agent.finalize(
            actx,
            output_text=output_text,
            whitelist=tool_ctx.citation_whitelist,
            citation_sources=tool_ctx.citation_sources,
            usage=usage,
        )
        run.output_json = output_json
        run.token_usage_json = usage
        # Token counts only — no pricing tables; consumers treat this as an
        # estimate derived from summed per-iteration usage.
        run.cost_json = {"estimated": True, **usage}
        run.status = AgentRunStatus.COMPLETED
        run.finished_at = _now()
        await self._reconcile_mission_task(run)
        await self.db.commit()

        summary = output_json.get("message") or output_json.get("novelty_summary") or ""
        await emitter.completed(summary, citations, usage)
        self._schedule_autopilot_continuation(run)
        return run

    @staticmethod
    def _schedule_autopilot_continuation(run: AgentRun) -> None:
        context = dict(run.input_json.get("context") or {})
        if not bool(context.get("autopilot")):
            return
        mission_id = context.get("mission_id")
        policy = context.get("autopilot_policy")
        if not mission_id or not isinstance(policy, dict):
            return
        try:
            from researchos.common.celery_app import get_celery_client

            get_celery_client().send_task(
                "orchestration.advance",
                args=[str(run.project_id), str(mission_id), str(run.user_id), policy],
                queue="default",
            )
        except Exception as exc:  # noqa: BLE001 - coordinator remains resumable by API
            logger.warning(
                "autopilot_continuation_dispatch_failed",
                run_id=str(run.id),
                error=str(exc),
            )

    async def _run_loop(
        self,
        agent: Agent,
        actx: AgentContext,
        tool_ctx: ToolContext,
        broker: ToolBroker,
        emitter: EventEmitter,
        llm: LLMProvider,
        effective_tools: set[str],
    ) -> tuple[str, dict]:
        messages = await agent.build_prompt(actx)
        llm_tools = [
            LLMTool(
                name=TOOL_REGISTRY[t].name,
                description=TOOL_REGISTRY[t].description,
                parameters=TOOL_REGISTRY[t].parameters,
            )
            for t in sorted(effective_tools)
            if t in TOOL_REGISTRY
        ]

        usage_total: dict = {"input_tokens": 0, "output_tokens": 0}
        tool_budget = (
            agent.max_tool_calls
            if agent.max_tool_calls is not None
            else self.settings.agent_max_tool_calls
        )
        tool_count = 0
        denied_count = 0
        iteration = 0
        synthesis = False
        prevalidated = False

        # Hard cap: safety against pathological providers that keep requesting
        # tools without ever exhausting the executed-call budget.
        while iteration < tool_budget + 4:
            iteration += 1
            if await is_cancel_requested(actx.run.id):
                raise AgentCancelledError()

            iter_text = ""
            requested: list[ToolCall] = []
            async for event in llm.stream(
                messages=messages,
                tools=([] if synthesis else llm_tools),
                response_schema=agent.response_schema,
                force_structured=synthesis and agent.response_schema is not None,
            ):
                if isinstance(event, TextDelta):
                    iter_text += event.text
                    await emitter.token(event.text)
                elif isinstance(event, ToolCall):
                    requested.append(event)
                elif isinstance(event, Usage):
                    usage_total["input_tokens"] += event.input_tokens
                    usage_total["output_tokens"] += event.output_tokens
                elif isinstance(event, StreamDone):
                    pass

            if not requested or synthesis:
                if not prevalidated:
                    feedback = await agent.prevalidate(actx, iter_text)
                    if feedback is not None:
                        # One corrective re-stream: show the model its own
                        # answer plus the validation feedback.
                        prevalidated = True
                        messages.append(LLMMessage(role="assistant", content=iter_text))
                        messages.append(LLMMessage(role="user", content=feedback))
                        continue
                return iter_text, usage_total

            messages.append(LLMMessage(role="assistant", content=iter_text, tool_calls=requested))
            # Sequential execution: the shared AsyncSession forbids concurrent
            # DB use; parallel safety comes from the seq allocator, not here.
            for call in requested:
                if await is_cancel_requested(actx.run.id):
                    raise AgentCancelledError()
                if tool_count >= tool_budget:
                    result: dict = {
                        "error": {
                            "type": "tool_budget_exhausted",
                            "message": "No tool calls remaining; produce your final answer.",
                        }
                    }
                else:
                    try:
                        result = await broker.execute(call.name, call.arguments)
                        tool_count += 1
                    except ToolDenied:
                        # Hallucinated tool names become a recoverable
                        # self-correction signal instead of failing the run.
                        denied_count += 1
                        if denied_count > 2:
                            raise
                        tool_count += 1
                        result = {
                            "error": {
                                "type": "tool_not_available",
                                "message": (
                                    f"Tool '{call.name}' is not available. "
                                    f"Available tools: {sorted(effective_tools)}"
                                ),
                            }
                        }
                messages.append(
                    LLMMessage(
                        role="tool",
                        name=call.name,
                        tool_call_id=call.id,
                        content=json.dumps(result),
                    )
                )
            if tool_count >= tool_budget:
                synthesis = True
                messages.append(LLMMessage(role="user", content=_SYNTHESIS_NUDGE))

        raise AppError(
            "Agent exceeded its iteration limit without producing a final answer.",
            code="llm_error",
            http_status=502,
        )

    async def _recover_session(self, run_id: uuid.UUID) -> AgentRun | None:
        """Roll back and re-fetch the run so finalization writes onto a clean
        session (a timeout cancellation can interrupt a pending DB await)."""

        await self.db.rollback()
        return await AgentRunRepository(self.db).get_unscoped(run_id)

    async def _finalize_failed(
        self, run: AgentRun, emitter: EventEmitter, error: str, *, code: str = "agent_error"
    ) -> None:
        run.status = AgentRunStatus.FAILED
        run.error_json = {"message": error, "code": code}
        run.finished_at = _now()
        await self._reconcile_mission_task(run)
        await self.db.commit()
        await emitter.failed(error, code)

    async def _finalize_cancelled(self, run: AgentRun, emitter: EventEmitter) -> None:
        run.status = AgentRunStatus.CANCELLED
        run.finished_at = _now()
        await self._reconcile_mission_task(run)
        await self.db.commit()
        await emitter.cancelled()

    async def _reconcile_mission_task(self, run: AgentRun) -> None:
        """Best-effort import boundary kept local to avoid runtime cycles."""

        try:
            from researchos.orchestration.service import OrchestrationService

            async with self.db.begin_nested():
                await OrchestrationService(self.db).reconcile_run(run)
        except Exception as exc:  # noqa: BLE001 - the AgentRun remains authoritative
            logger.exception(
                "mission_task_reconciliation_failed",
                run_id=str(run.id),
                error=str(exc),
            )


async def run_agent_run(run_id: str, *, http_client: httpx.AsyncClient | None = None) -> None:
    """Entry point used by the Celery task: opens a session and runs the agent."""

    async with get_sessionmaker()() as db:
        await AgentRuntime(db, http_client=http_client).run(uuid.UUID(run_id))
