"""API-side dispatch of figure render tasks.

The task name rides the existing ``experiments.*`` route, so the worker's
routing table needs no change.
"""

from __future__ import annotations

from researchos.common.celery_app import get_celery_client

FIGURE_RENDER_TASK = "experiments.render_figure"


def dispatch_figure_render(figure_id: str) -> None:
    """Enqueue a figure render on the ``experiments`` queue."""

    get_celery_client().send_task(FIGURE_RENDER_TASK, args=[figure_id], queue="experiments")
