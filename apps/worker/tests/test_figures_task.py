"""Figure render task wiring: registration name and queue routing."""

from __future__ import annotations

import researchos_worker.tasks.figures  # noqa: F401 - importing registers the task
from researchos_worker.app import app
from researchos_worker.queues import Queue


def test_render_figure_task_registered() -> None:
    assert "experiments.render_figure" in app.tasks


def test_render_figure_routes_to_experiments_queue() -> None:
    # The task name rides the existing experiments.* route; no routing change.
    assert app.conf.task_routes["experiments.*"]["queue"] == Queue.EXPERIMENTS
