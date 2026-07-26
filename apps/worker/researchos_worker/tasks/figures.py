"""Figure render task (``experiments`` queue).

All render logic lives in ``researchos.figures.render_job``; this task is only
the Celery entry point (mirrors ``tasks/agents.py``).
"""

from __future__ import annotations

import structlog
from researchos.common.asyncio_runner import run_async_task
from researchos.figures.render_job import run_figure_render

from ..app import app

logger = structlog.get_logger(__name__)


@app.task(name="experiments.render_figure")
def render_figure(figure_id: str) -> str:
    logger.info("figure_render_task_received", figure_id=figure_id)
    # Fresh event loop per task; loop-bound globals (DB engine, Redis client)
    # are disposed afterwards so consecutive tasks never collide.
    run_async_task(lambda: run_figure_render(figure_id))
    return figure_id
