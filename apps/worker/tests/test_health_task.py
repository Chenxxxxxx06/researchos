"""Tests for worker wiring and health tasks.

Tasks are invoked synchronously (calling the task object runs it in-process),
so no broker connection is required.
"""

from __future__ import annotations

from researchos_worker.app import app
from researchos_worker.queues import ALL_QUEUES, Queue
from researchos_worker.tasks.health import ping


def test_ping_runs_in_process() -> None:
    assert ping() == "pong"


def test_celery_app_configured() -> None:
    assert app.main == "researchos"
    assert app.conf.task_default_queue == Queue.DEFAULT.value


def test_queue_routes_cover_workloads() -> None:
    # The six planned workload queues plus the default queue exist.
    assert set(ALL_QUEUES) == {
        "agents",
        "ingestion",
        "runtime",
        "latex",
        "experiments",
        "skills",
        "default",
    }


def test_task_routing_maps_prefixes() -> None:
    routes = app.conf.task_routes
    assert routes["agents.*"]["queue"] == Queue.AGENTS
    assert routes["latex.*"]["queue"] == Queue.LATEX
