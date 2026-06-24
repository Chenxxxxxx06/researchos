"""API-side Celery client.

The API does not import worker task code; it dispatches tasks by name. The
worker registers the matching task (``agents.run_agent``). This keeps the API
and worker decoupled while sharing the same broker.
"""

from __future__ import annotations

from functools import lru_cache

from celery import Celery

from researchos.common.config import get_settings

AGENT_RUN_TASK = "agents.run_agent"


@lru_cache
def get_celery_client() -> Celery:
    settings = get_settings()
    return Celery("researchos-client", broker=settings.broker_url, backend=settings.result_backend)


def dispatch_agent_run(run_id: str) -> None:
    """Enqueue an agent run on the ``agents`` queue."""

    get_celery_client().send_task(AGENT_RUN_TASK, args=[run_id], queue="agents")
