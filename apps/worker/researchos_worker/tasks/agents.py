"""Agent execution task (``agents`` queue).

Runs an AgentRun through the runtime layer. All agent logic lives in
``researchos.agents.runtime``; this task is only the Celery entry point.

Time limits: the runtime's own ``asyncio.timeout`` (AGENT_RUN_TIMEOUT_SECONDS)
is the authoritative guard. The Celery soft/hard limits below are a backstop
(prefork/Unix) so a wedged event loop cannot poison the single-prefetch worker.
"""

from __future__ import annotations

import structlog
from researchos.agents.runtime import run_agent_run
from researchos.common.asyncio_runner import run_async_task
from researchos.common.config import get_settings

from ..app import app

logger = structlog.get_logger(__name__)

settings = get_settings()


@app.task(
    name="agents.run_agent",
    soft_time_limit=settings.agent_run_timeout_seconds + 60,
    time_limit=settings.agent_run_timeout_seconds + 120,
)
def run_agent(run_id: str) -> str:
    logger.info("agent_task_received", run_id=run_id)
    # Each task runs in a fresh event loop and disposes loop-bound globals (DB
    # engine, Redis client) afterwards, so consecutive tasks never collide.
    run_async_task(lambda: run_agent_run(run_id))
    return run_id
