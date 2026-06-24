"""Agent execution task (``agents`` queue).

Runs an AgentRun through the runtime layer. All agent logic lives in
``researchos.agents.runtime``; this task is only the Celery entry point.
"""

from __future__ import annotations

import structlog
from researchos.agents.runtime import run_agent_run
from researchos.common.asyncio_runner import run_async_task

from ..app import app

logger = structlog.get_logger(__name__)


@app.task(name="agents.run_agent")
def run_agent(run_id: str) -> str:
    logger.info("agent_task_received", run_id=run_id)
    # Each task runs in a fresh event loop and disposes loop-bound globals (DB
    # engine, Redis client) afterwards, so consecutive tasks never collide.
    run_async_task(lambda: run_agent_run(run_id))
    return run_id
