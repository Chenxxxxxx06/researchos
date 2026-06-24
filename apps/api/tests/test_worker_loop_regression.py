"""Regression test for the worker per-task event-loop fix.

Simulates two consecutive Celery tasks: each runs the agent runtime in its own
event loop via ``run_async_task`` (exactly as the worker does). Before the fix,
the second invocation failed with ``Event loop is closed`` /
``got Future attached to a different loop`` because the global async DB engine
and Redis client leaked across loops. This test is synchronous so it can drive
``asyncio.run`` itself.
"""

from __future__ import annotations

import uuid

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.agents.runtime import run_agent_run
from researchos.common.asyncio_runner import run_async_task
from researchos.common.db import get_sessionmaker
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.research.providers.base import PaperResult
from researchos.research.service import IdeaService, PaperService


async def _setup_two_critic_runs() -> list[str]:
    async with get_sessionmaker()() as db:
        user, org = await AuthService(db).register(
            email="loop@example.com", password="password123", display_name="Loop"
        )
        project = await ProjectService(db).create_project(
            user, organization_id=org.id, name="P", description=None, field=None
        )
        await PaperService(db).import_papers(
            user,
            project.id,
            [
                PaperResult(
                    source="arxiv",
                    external_id="2401.01234",
                    title="Lib",
                    url="http://arxiv.org/abs/2401.01234",
                )
            ],
        )
        run_ids: list[str] = []
        for _ in range(2):
            idea = await IdeaService(db).create(
                user, project.id, title="Idea", description="d", hypothesis=None
            )
            run = await AgentRunRepository(db).create(
                AgentRun(
                    project_id=project.id,
                    user_id=user.id,
                    agent_type=AgentType.CRITIC,
                    status=AgentRunStatus.QUEUED,
                    input_json={"message": "c", "context": {"idea_id": str(idea.id)}},
                )
            )
            await db.commit()
            run_ids.append(str(run.id))
        return run_ids


async def _statuses(run_ids: list[str]) -> list[str]:
    async with get_sessionmaker()() as db:
        repo = AgentRunRepository(db)
        out: list[str] = []
        for rid in run_ids:
            run = await repo.get_unscoped(uuid.UUID(rid))
            out.append(run.status.value if run else "missing")
        return out


def test_two_sequential_agent_tasks_do_not_leak_event_loop() -> None:
    run_ids = run_async_task(_setup_two_critic_runs)

    # Two independent "Celery tasks", each in its own event loop.
    run_async_task(lambda: run_agent_run(run_ids[0]))
    run_async_task(lambda: run_agent_run(run_ids[1]))

    statuses = run_async_task(lambda: _statuses(run_ids))
    assert statuses == ["completed", "completed"]
