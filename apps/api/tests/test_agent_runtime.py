"""Agent runtime tests using the mock LLM provider and an injected arXiv client.

No network and no LLM API key. Covers the full run lifecycle, tool-call
persistence, event persistence, citation integrity, and the critic path.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType, ToolCallStatus
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

    tool_calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert any(
        t.tool_name == "paper.search" and t.status == ToolCallStatus.SUCCEEDED for t in tool_calls
    )

    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    types = {e.event_type for e in events}
    assert {
        "agent.run.started",
        "agent.run.tool_call.started",
        "agent.run.tool_call.completed",
        "agent.run.completed",
    } <= types
    # Token events are not persisted (live-only).
    assert "agent.run.token" not in types


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
