"""Agent runtime tests using the mock LLM provider and an injected arXiv client.

No network and no LLM API key. Covers the full run lifecycle (multi-turn tool
use), tool-call/event persistence, usage summing, citation integrity, the
critic path, cancellation, timeout, and ToolDenied recovery.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.cancellation import request_cancel
from researchos.agents.enums import AgentRunStatus, AgentType, ToolCallStatus
from researchos.agents.llm.base import (
    LLMMessage,
    LLMTool,
    StreamDone,
    StreamEvent,
    TextDelta,
    ToolCall,
    Usage,
)
from researchos.agents.models import AgentRun
from researchos.agents.repository import (
    AgentRunEventRepository,
    AgentRunRepository,
    ToolCallRepository,
)
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.citations import filter_citations
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.research.providers.base import PaperResult
from researchos.research.repository import CritiqueRepository
from researchos.research.service import IdeaService, PaperService

_FIXTURE = (Path(__file__).parent / "fixtures" / "arxiv_sample.xml").read_text(encoding="utf-8")


def _mock_arxiv() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_FIXTURE)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _setup(db: AsyncSession, email: str):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Runner"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    return user, project


# --- pure citation guard -----------------------------------------------------
def test_filter_citations_drops_unbacked() -> None:
    kept, dropped = filter_citations(["arxiv:real", "arxiv:fake", "arxiv:real"], {"arxiv:real"})
    assert kept == ["arxiv:real"]
    assert dropped == ["arxiv:fake"]


# --- research run ------------------------------------------------------------
async def test_research_run_full_lifecycle(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "rt-research@example.com")
    run = await AgentRunRepository(db_session).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.RESEARCH,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "vision language", "context": {}},
        )
    )
    await db_session.commit()

    async with _mock_arxiv() as http:
        await AgentRuntime(db_session, http_client=http).run(run.id)

    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED
    # Citations are exactly the papers actually retrieved (no fabrication).
    assert set(run.output_json["citations"]) == {"arxiv:2401.01234", "arxiv:2312.05678"}

    # The mock now scripts a genuine multi-turn conversation: two tool
    # iterations (name-sorted: library.list then paper.search), seqs 0..N-1.
    tool_calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert len(tool_calls) >= 2
    assert [t.tool_name for t in tool_calls[:2]] == ["library.list", "paper.search"]
    assert all(t.status == ToolCallStatus.SUCCEEDED for t in tool_calls)
    assert [t.seq for t in tool_calls] == list(range(len(tool_calls)))

    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    types = {e.event_type for e in events}
    assert {
        "agent.run.started",
        "agent.run.tool_call.started",
        "agent.run.tool_call.completed",
        "agent.run.completed",
    } <= types
    # Token events are not persisted (live-only); persisted seqs are monotonic.
    assert "agent.run.token" not in types
    assert [e.seq for e in events] == list(range(len(events)))

    # Usage is SUMMED across iterations: two tool turns (12 input each) plus
    # the final answer turn (20 input, len(text)//4 output).
    expected_output = max(1, len(run.output_json["message"]) // 4)
    assert run.token_usage_json == {"input_tokens": 44, "output_tokens": expected_output}


# --- critic run --------------------------------------------------------------
async def test_critic_run_persists_critique(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "rt-critic@example.com")

    await PaperService(db_session).import_papers(
        user,
        project.id,
        [
            PaperResult(
                source="arxiv",
                external_id="2401.01234",
                title="Lib Paper",
                url="http://arxiv.org/abs/2401.01234",
            )
        ],
    )
    idea = await IdeaService(db_session).create(
        user, project.id, title="My idea", description="d", hypothesis=None
    )

    run = await AgentRunRepository(db_session).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CRITIC,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "Critique", "context": {"idea_id": str(idea.id)}},
        )
    )
    await db_session.commit()

    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED

    critiques = await CritiqueRepository(db_session).list_by_idea(project.id, idea.id)
    assert len(critiques) == 1
    # Citations only reference the library paper (no fabrication).
    assert set(critiques[0].citations_json) <= {"arxiv:2401.01234"}
    assert critiques[0].novelty_summary


# --- cancellation, timeout, denied-tool recovery -----------------------------
async def _research_run(db: AsyncSession, email: str) -> AgentRun:
    user, project = await _setup(db, email)
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.RESEARCH,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "cancel me", "context": {}},
        )
    )
    await db.commit()
    return run


async def test_invalid_explicit_llm_config_fails_run_durably(
    db_session: AsyncSession,
) -> None:
    run = await _research_run(db_session, "rt-llm-invalid@example.com")
    run.input_json = {
        "message": "use missing model",
        "context": {"llm_config_id": str(uuid.uuid4())},
    }
    await db_session.commit()

    await AgentRuntime(db_session).run(run.id)

    await db_session.refresh(run)
    assert run.status == AgentRunStatus.FAILED
    assert run.error_json["code"] == "not_found"
    assert "LLM config" in run.error_json["message"]


class CancellingProvider:
    """Sets the cooperative cancel flag from inside its second stream call."""

    name = "cancelling"

    def __init__(self, run_id) -> None:
        self.run_id = run_id
        self.stream_calls = 0

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        self.stream_calls += 1
        if self.stream_calls >= 2:
            await request_cancel(self.run_id)
        yield ToolCall(id=f"call_{self.stream_calls}", name="library.list", arguments={})
        yield Usage(input_tokens=1, output_tokens=0)
        yield StreamDone(stop_reason="tool_use")


async def test_mid_loop_cancellation(db_session: AsyncSession) -> None:
    run = await _research_run(db_session, "rt-cancel@example.com")

    await AgentRuntime(db_session, llm=CancellingProvider(run.id)).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.CANCELLED
    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    types = [e.event_type for e in events]
    assert "agent.run.cancelled" in types
    assert "agent.run.completed" not in types


class SlowProvider:
    name = "slow"

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        await asyncio.sleep(5)
        yield TextDelta("too late")
        yield StreamDone(stop_reason="stop")


async def test_run_timeout_fails_with_code(db_session: AsyncSession) -> None:
    run = await _research_run(db_session, "rt-timeout@example.com")

    runtime = AgentRuntime(db_session, llm=SlowProvider())
    runtime.settings = runtime.settings.model_copy(update={"agent_run_timeout_seconds": 0})
    await runtime.run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.FAILED
    assert run.error_json == {"message": "Agent run timed out.", "code": "timeout"}
    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    failed = [e for e in events if e.event_type == "agent.run.failed"]
    assert len(failed) == 1
    assert failed[0].payload_json["code"] == "timeout"


class HallucinatingProvider:
    """Requests a nonexistent tool once, then produces a normal answer."""

    name = "hallucinating"

    def __init__(self) -> None:
        self.stream_calls = 0

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        self.stream_calls += 1
        if self.stream_calls == 1:
            yield ToolCall(id="call_1", name="does.not.exist", arguments={})
            yield Usage(input_tokens=1, output_tokens=0)
            yield StreamDone(stop_reason="tool_use")
            return
        yield TextDelta("Recovered without that tool.")
        yield Usage(input_tokens=1, output_tokens=1)
        yield StreamDone(stop_reason="stop")


async def test_hallucinated_tool_is_recoverable(db_session: AsyncSession) -> None:
    run = await _research_run(db_session, "rt-denied@example.com")

    await AgentRuntime(db_session, llm=HallucinatingProvider()).run(run.id)
    await db_session.refresh(run)

    # The run completes; the denied call is persisted as a FAILED tool_call.
    assert run.status == AgentRunStatus.COMPLETED
    assert run.output_json["message"] == "Recovered without that tool."
    tool_calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "does.not.exist"
    assert tool_calls[0].status == ToolCallStatus.FAILED
