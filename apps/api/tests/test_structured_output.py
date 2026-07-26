"""Structured-output runtime gate tests (DB + injected providers, no network).

A garbage LLM answer must FAIL the run with a typed error — never persist an
empty critique on a COMPLETED run. The synthesis round (budget exhaustion +
``force_structured``) must still produce a valid structured result.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
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
from researchos.agents.repository import AgentRunEventRepository, AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.critic_agent import CriticAgent
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.research.repository import CritiqueRepository
from researchos.research.service import IdeaService


async def _critic_run(db: AsyncSession, email: str) -> tuple[AgentRun, object, object]:
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Runner"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    idea = await IdeaService(db).create(
        user, project.id, title="My idea", description="d", hypothesis=None
    )
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CRITIC,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "Critique", "context": {"idea_id": str(idea.id)}},
        )
    )
    await db.commit()
    return run, project, idea


class GarbageProvider:
    """Streams prose that is not JSON — a misbehaving real model."""

    name = "garbage"

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        yield TextDelta("I am sorry, I cannot ")
        yield TextDelta("produce the requested object.")
        yield Usage(input_tokens=5, output_tokens=5)
        yield StreamDone(stop_reason="stop")


class ForceStructuredOnlyProvider:
    """Emits valid JSON ONLY under force_structured; otherwise requests tools."""

    name = "force-only"

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
        if force_structured:
            yield TextDelta(json.dumps({"novelty_summary": "forced synthesis", "citations": []}))
            yield Usage(input_tokens=3, output_tokens=3)
            yield StreamDone(stop_reason="stop")
            return
        yield ToolCall(id=f"call_{self.stream_calls}", name="library.list", arguments={})
        yield Usage(input_tokens=2, output_tokens=0)
        yield StreamDone(stop_reason="tool_use")


async def test_unparseable_structured_output_fails_run(db_session: AsyncSession) -> None:
    run, project, idea = await _critic_run(db_session, "so-garbage@example.com")

    await AgentRuntime(db_session, llm=GarbageProvider()).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.FAILED
    assert run.error_json["code"] == "structured_output_parse_error"
    # No empty critique was persisted.
    critiques = await CritiqueRepository(db_session).list_by_idea(project.id, idea.id)
    assert critiques == []
    # The failed event carries the typed code.
    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    failed = [e for e in events if e.event_type == "agent.run.failed"]
    assert len(failed) == 1
    assert failed[0].payload_json["code"] == "structured_output_parse_error"
    assert not any(e.event_type == "agent.run.completed" for e in events)


async def test_critic_via_standard_mock_still_completes(db_session: AsyncSession) -> None:
    run, project, idea = await _critic_run(db_session, "so-mock@example.com")

    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.COMPLETED
    # output_json parses and citations were filtered against the whitelist
    # (empty library + empty tool results => no citations survive).
    assert run.output_json["novelty_summary"]
    assert run.output_json["citations"] == []
    critiques = await CritiqueRepository(db_session).list_by_idea(project.id, idea.id)
    assert len(critiques) == 1


async def test_force_structured_synthesis_round_completes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Budget 0: every requested call gets a budget-exhausted stub, then the
    # synthesis round runs with force_structured=True.
    monkeypatch.setattr(CriticAgent, "max_tool_calls", 0)
    run, project, idea = await _critic_run(db_session, "so-force@example.com")

    provider = ForceStructuredOnlyProvider()
    await AgentRuntime(db_session, llm=provider).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.COMPLETED
    assert run.output_json["novelty_summary"] == "forced synthesis"
    critiques = await CritiqueRepository(db_session).list_by_idea(project.id, idea.id)
    assert len(critiques) == 1
    # Two stream calls: the tool-requesting turn and the forced synthesis turn.
    assert provider.stream_calls == 2
