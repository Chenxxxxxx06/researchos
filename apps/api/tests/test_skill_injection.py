"""Skill runtime injection tests (DB, mock provider, no network).

Enabled project skills must demonstrably change agent behavior: prompt
fragments injected (mock surfaces the ``[skills-active]`` marker), active
skills recorded on the run and in the started event, tool grants bounded by
allowlist ∩ registry, and the PINNED installation version used.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunEventRepository, AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.critic_agent import CriticAgent
from researchos.agents.runtime.runtime import _effective_tools
from researchos.agents.runtime.skills_injection import render_skill_block, skill_tool_grants
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.skills.enums import SkillModule, SkillVisibility
from researchos.skills.models import Skill, SkillInstallation, SkillVersion
from researchos.skills.schemas import CustomSkillRequest
from researchos.skills.service import RuntimeSkill, SkillService

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


def _skill_request(slug: str, *, version: str = "1.0.0") -> CustomSkillRequest:
    return CustomSkillRequest(
        slug=slug,
        name=f"Skill {slug}",
        version=version,
        description="Test skill",
        category="general",
        modules=[SkillModule.RESEARCH],
        prompt_template="Respond in a {{tone}} tone.",
        workflow=["Analyze", "Answer"],
        tool_permissions=["library.list"],
        config_schema={},
    )


async def _research_run(db: AsyncSession, user, project) -> AgentRun:
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.RESEARCH,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "vision language", "context": {}},
        )
    )
    await db.commit()
    return run


async def test_enabled_skill_injected_and_recorded(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "ski-on@example.com")
    service = SkillService(db_session)
    await service.create_custom(user, project.id, _skill_request("tone-skill"))
    await service.install(user, project.id, "tone-skill")

    run = await _research_run(db_session, user, project)
    async with _mock_arxiv() as http:
        await AgentRuntime(db_session, http_client=http).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.COMPLETED
    assert run.skill_ids_json == [{"slug": "tone-skill", "version": "1.0.0"}]
    # The mock provider marks prompts carrying the skills block.
    assert run.output_json["message"].startswith("[skills-active] ")
    # The started event carries the active skills.
    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    started = [e for e in events if e.event_type == "agent.run.started"]
    assert len(started) == 1
    assert started[0].payload_json["skills"] == [{"slug": "tone-skill", "version": "1.0.0"}]


async def test_disabled_installation_injects_nothing(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "ski-off@example.com")
    service = SkillService(db_session)
    await service.create_custom(user, project.id, _skill_request("quiet-skill"))
    await service.install(user, project.id, "quiet-skill")
    await service.toggle(user, project.id, "quiet-skill", enabled=False)

    run = await _research_run(db_session, user, project)
    async with _mock_arxiv() as http:
        await AgentRuntime(db_session, http_client=http).run(run.id)
    await db_session.refresh(run)

    assert run.status == AgentRunStatus.COMPLETED
    assert run.skill_ids_json == []
    assert not run.output_json["message"].startswith("[skills-active] ")
    events = await AgentRunEventRepository(db_session).list_after(run.id, after_seq=-1)
    started = [e for e in events if e.event_type == "agent.run.started"]
    assert started[0].payload_json["skills"] == []


async def test_runtime_uses_pinned_version_not_latest(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "ski-pin@example.com")
    service = SkillService(db_session)
    await service.create_custom(user, project.id, _skill_request("pinned-skill"))
    await service.install(user, project.id, "pinned-skill")
    # Publish a newer version AFTER installation: the pin must hold.
    await service.update_custom(
        user, project.id, "pinned-skill", _skill_request("pinned-skill", version="2.0.0")
    )

    skills = await service.list_enabled_for_runtime(project.id, SkillModule.RESEARCH)
    assert [s.version for s in skills] == ["1.0.0"]


async def test_tool_permissions_filtered_and_cap_respected(db_session: AsyncSession) -> None:
    user, project = await _setup(db_session, "ski-cap@example.com")
    service = SkillService(db_session)

    # Manifest with an undeclarable tool, crafted directly (the builder API
    # rejects unknown tools, but old/imported rows could carry them).
    skill = Skill(
        slug="sneaky-skill",
        name="Sneaky",
        description="",
        author="custom",
        category="general",
        visibility=SkillVisibility.CUSTOM,
        project_id=project.id,
        created_by=user.id,
    )
    db_session.add(skill)
    await db_session.flush()
    version = SkillVersion(
        skill_id=skill.id,
        version="1.0.0",
        manifest_json={
            "modules": ["research"],
            "prompt_template": "p",
            "workflow": [],
            "tool_permissions": ["library.list", "workspace.delete_everything"],
        },
    )
    db_session.add(version)
    await db_session.flush()
    db_session.add(
        SkillInstallation(
            project_id=project.id,
            skill_id=skill.id,
            skill_version_id=version.id,
            enabled=True,
            installed_by=user.id,
        )
    )
    await db_session.commit()

    skills = await service.list_enabled_for_runtime(project.id, SkillModule.RESEARCH)
    assert [s.slug for s in skills] == ["sneaky-skill"]
    assert skills[0].tool_permissions == ["library.list"]

    # Cap 5: six enabled research skills -> five returned.
    for i in range(5):
        await service.create_custom(user, project.id, _skill_request(f"extra-skill-{i}"))
        await service.install(user, project.id, f"extra-skill-{i}")
    skills = await service.list_enabled_for_runtime(project.id, SkillModule.RESEARCH)
    assert len(skills) == 5


def test_effective_tools_union_intersect_registry() -> None:
    skill = RuntimeSkill(
        slug="widener",
        name="Widener",
        version="1.0.0",
        prompt_template="p",
        # paper.search is allowlisted AND registered; memory.read is
        # allowlisted but NOT in TOOL_REGISTRY -> must not materialize.
        tool_permissions=["paper.search", "memory.read"],
    )
    tools = _effective_tools(CriticAgent(), [skill])
    assert "paper.search" in tools  # widened by the skill
    assert "library.list" in tools  # the agent's own tool
    assert "memory.read" not in tools  # declared but unregistered
    assert skill_tool_grants([skill]) == {
        "paper.search": "widener",
        "memory.read": "widener",
    }


def test_render_skill_block_substitution_and_budget() -> None:
    skill = RuntimeSkill(
        slug="tone",
        name="Tone",
        version="1.0.0",
        prompt_template="Respond in a {{tone}} tone; keep {{unknown}} as-is.",
        workflow=["Analyze", "Answer"],
        settings={"tone": "formal"},
    )
    block = render_skill_block([skill])
    assert block.startswith("## Active skills")
    assert "Respond in a formal tone; keep {{unknown}} as-is." in block
    assert "Suggested workflow: 1) Analyze; 2) Answer" in block
    assert render_skill_block([]) == ""

    long_skill = RuntimeSkill(
        slug="long",
        name="Long",
        version="1.0.0",
        prompt_template="x" * 500,
    )
    dropped_skill = RuntimeSkill(
        slug="dropped",
        name="Dropped",
        version="1.0.0",
        prompt_template="should not appear",
    )
    block = render_skill_block([long_skill, dropped_skill], char_budget=100)
    assert "[truncated]" in block
    assert "should not appear" not in block
