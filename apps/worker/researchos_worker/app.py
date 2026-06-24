"""Celery application factory.

Reuses the shared ``Settings`` (broker/result backend) and structured logging
from the API package so the worker and API agree on infrastructure.
"""

from __future__ import annotations

from celery import Celery
from researchos.common.config import get_settings
from researchos.common.logging import configure_logging

from .queues import TASK_ROUTES, Queue


def create_celery() -> Celery:
    configure_logging()
    settings = get_settings()

    celery_app = Celery(
        "researchos",
        broker=settings.broker_url,
        backend=settings.result_backend,
        include=["researchos_worker.tasks.health", "researchos_worker.tasks.agents"],
    )

    celery_app.conf.update(
        task_default_queue=Queue.DEFAULT.value,
        task_routes=TASK_ROUTES,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
        timezone="UTC",
        enable_utc=True,
    )
    return celery_app


app = create_celery()
