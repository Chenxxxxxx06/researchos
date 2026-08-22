"""Golden typed-agent chain from paper extraction to writing and figures."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from researchos.agents.enums import AgentType
from researchos.agents.llm.mock import MockLLMProvider
from researchos.agents.models import AgentRun
from researchos.agents.runtime.runtime import AgentRuntime
from researchos.identity.models import User
from researchos.knowledge.models import MissionPaper
from researchos.research.enums import PaperIngestStatus, PaperSectionKind
from researchos.research.models import Paper, PaperSection

from .helpers import csrf_headers, register


async def test_typed_research_program_agents_complete_with_mock_protocol(
    client, db_session, monkeypatch
) -> None:
    email = "program-agents@example.com"
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = (
        await client.post(
            "/projects",
            json={"organization_id": org_id, "name": "Program agents"},
            headers=csrf_headers(client),
        )
    ).json()
    mission = (
        await client.post(
            f"/projects/{project['id']}/missions",
            json={"topic": "Robust calibration", "objective": "Build a pilot-first method"},
            headers=csrf_headers(client),
        )
    ).json()
    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    paper = Paper(
        project_id=uuid.UUID(project["id"]),
        source="arxiv",
        external_id="2608.00001",
        title="Robust calibration with controlled evaluation",
        abstract="A calibration method with a controlled benchmark.",
        authors_json=["Researcher"],
        venue="Test Venue",
        url="https://arxiv.org/abs/2608.00001",
        ingest_status=PaperIngestStatus.SUCCEEDED,
        imported_by=user.id,
    )
    db_session.add(paper)
    await db_session.flush()
    section = PaperSection(
        paper_id=paper.id,
        seq=1,
        level=2,
        heading="Method and experiments",
        body=(
            "The method estimates uncertainty with a calibration loss and evaluates a "
            "controlled benchmark with a held-out split."
        ),
        char_count=128,
        kind=PaperSectionKind.METHOD,
    )
    db_session.add(section)
    db_session.add(
        MissionPaper(
            project_id=paper.project_id,
            mission_id=uuid.UUID(mission["id"]),
            paper_id=paper.id,
            inclusion_reason="Core evidence",
            included_by=user.id,
        )
    )
    await db_session.commit()
    monkeypatch.setattr("researchos.agents.service.dispatch_agent_run", lambda _run_id: None)

    async def run(agent_type: AgentType, context: dict) -> AgentRun:
        response = await client.post(
            f"/projects/{project['id']}/agents/runs",
            json={
                "agent_type": agent_type.value,
                "message": f"Execute the {agent_type.value} contract.",
                "context": context,
            },
            headers=csrf_headers(client),
        )
        assert response.status_code == 201, response.text
        run_id = uuid.UUID(response.json()["agent_run_id"])
        result = await AgentRuntime(db_session, llm=MockLLMProvider()).run(run_id)
        assert result is not None
        assert result.status.value == "completed", result.error_json
        return result

    reading = await run(
        AgentType.READING_CARD,
        {
            "mission_id": mission["id"],
            "paper_id": str(paper.id),
            "section_kinds": ["method"],
        },
    )
    assert reading.output_json["tuple_count"] >= 2

    await client.post(
        f"/projects/{project['id']}/orchestration/missions/{mission['id']}/bootstrap",
        headers=csrf_headers(client),
    )
    idea = await run(AgentType.IDEA_EXPLORER, {"mission_id": mission["id"]})
    assert idea.output_json["directions"]
    benchmark = await run(AgentType.BENCHMARK, {"mission_id": mission["id"]})
    assert benchmark.output_json["pilot_matrix"]
    viewer = await run(AgentType.VIEWER, {"mission_id": mission["id"]})
    assert viewer.output_json["verdict"] in {"pass", "revise", "reject"}
    leader = await run(AgentType.LEADER, {"mission_id": mission["id"]})
    assert leader.output_json["decision"]
    writer = await run(
        AgentType.WRITER,
        {"mission_id": mission["id"], "venue": "neurips", "section": "methods"},
    )
    assert writer.output_json["latex"].startswith("\\section")
    drawer = await run(AgentType.DRAWER, {"mission_id": mission["id"]})
    assert drawer.output_json["mermaid_valid"] is True
    progress = await run(AgentType.PROGRESS, {"mission_id": mission["id"]})
    assert 0 <= progress.output_json["progress_percent"] <= 100

    capabilities = await client.get(f"/projects/{project['id']}/agents/capabilities")
    assert capabilities.status_code == 200
    assert len(capabilities.json()) >= 17
