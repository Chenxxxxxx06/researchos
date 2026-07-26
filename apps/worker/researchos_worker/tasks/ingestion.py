"""Paper full-text ingestion task (``ingestion`` queue).

All ingestion logic lives in ``researchos.research.ingest``; this task is only
the Celery entry point. Idempotent under acks_late redelivery (the ingest run
fully replaces a paper's sections).
"""

from __future__ import annotations

import uuid

import structlog
from researchos.common.asyncio_runner import run_async_task
from researchos.research.ingest import ingest_paper

from ..app import app

logger = structlog.get_logger(__name__)


@app.task(name="ingestion.paper_fulltext")
def paper_fulltext(paper_id: str) -> str:
    logger.info("ingestion_task_received", paper_id=paper_id)
    # Fresh event loop per task; loop-bound globals (DB engine, Redis) are
    # disposed afterwards so consecutive tasks never collide.
    run_async_task(lambda: ingest_paper(uuid.UUID(paper_id)))
    return paper_id
