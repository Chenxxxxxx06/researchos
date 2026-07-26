"""Agent task Celery time limits (pure import test, no broker).

The runtime's own asyncio timeout is authoritative; the Celery limits are a
backstop so a wedged event loop cannot poison the single-prefetch worker.
"""

from __future__ import annotations

from researchos.common.config import get_settings

from researchos_worker.tasks.agents import run_agent


def test_agents_task_time_limits_derived_from_settings() -> None:
    settings = get_settings()
    assert run_agent.soft_time_limit == settings.agent_run_timeout_seconds + 60
    assert run_agent.time_limit == settings.agent_run_timeout_seconds + 120


def test_agents_task_name_unchanged() -> None:
    assert run_agent.name == "agents.run_agent"
