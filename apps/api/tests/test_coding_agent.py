"""Coding agent runtime test (mock LLM): proposes a pending patch, never writes."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.identity.service import AuthService
from researchos.patches.enums import PatchStatus
from researchos.patches.repository import PatchRepository
from researchos.projects.service import ProjectService
from researchos.workspace import fs


async def test_coding_agent_creates_pending_patch(db_session: AsyncSession) -> None:
    user, org = await AuthService(db_session).register(
        email="coder@example.com", password="password123", display_name="Coder"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )

    run = await AgentRunRepository(db_session).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CODING,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "add notes", "context": {}},
        )
    )
    await db_session.commit()

    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED

    # A pending patch was proposed, referencing this run.
    patches, total = await PatchRepository(db_session).list_by_project(
        project.id, limit=10, offset=0
    )
    assert total == 1
    patch = patches[0]
    assert patch.status == PatchStatus.PENDING
    assert patch.agent_run_id == run.id
    assert patch.files[0].path == "AGENT_NOTES.md"
    assert patch.files[0].change_type.value == "create"

    # The agent did NOT write the file — it only proposed it.
    assert fs.current_sha(project.id, "AGENT_NOTES.md") is None
