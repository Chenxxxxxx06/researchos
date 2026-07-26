"""Bearer-auth NDJSON ingest endpoint.

Deliberately a separate router with NO cookie/CSRF dependencies — GPU
training scripts POST here with only the ``Authorization: Bearer rosit_...``
header. Membership semantics: the run must belong to the token's project
(404 otherwise, hiding existence).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request

from researchos.common.deps import DbSession

from .ingest import IngestService
from .schemas import IngestResult

router = APIRouter(prefix="/ingest", tags=["experiments-ingest"])


@router.post("/experiment-runs/{run_id}", response_model=IngestResult)
async def ingest_run_telemetry(
    run_id: uuid.UUID,
    request: Request,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> IngestResult:
    service = IngestService(db)
    token, run = await service.authenticate(authorization, run_id)
    body = await request.body()
    return await service.process(token, run, body)
