"""Bounded local experiment runner tasks."""

from __future__ import annotations

import structlog
from researchos.common.asyncio_runner import run_async_task
from researchos.experiments.local_runner import (
    mark_local_autopilot_failure,
    run_local_autopilot_experiment,
)

from ..app import app

logger = structlog.get_logger(__name__)


@app.task(name="experiments.run_local")
def run_local_experiment(
    run_id: str,
    task_id: str,
    user_id: str,
    policy: dict,
) -> str:
    logger.info("local_experiment_received", run_id=run_id, task_id=task_id)
    try:
        run_async_task(lambda: run_local_autopilot_experiment(run_id, task_id, user_id, policy))
    except Exception as error:  # noqa: BLE001 - persist failure before Celery records it
        message = str(error)
        logger.exception("local_experiment_failed", run_id=run_id, task_id=task_id)
        run_async_task(lambda: mark_local_autopilot_failure(run_id, task_id, user_id, message))
    return run_id
