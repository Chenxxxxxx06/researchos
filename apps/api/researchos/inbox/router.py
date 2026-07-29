"""Project-scoped Research Inbox endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    AnalyzeInboxItemRequest,
    AnalyzeInboxItemResponse,
    CreateInboxItemRequest,
    InboxItemResponse,
)
from .service import ResearchInboxService

router = APIRouter(prefix="/projects/{project_id}/inbox", tags=["research-inbox"])


@router.get("", response_model=list[InboxItemResponse])
async def list_items(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[InboxItemResponse]:
    items = await ResearchInboxService(db).list_items(user, project_id)
    return [InboxItemResponse.model_validate(item) for item in items]


@router.post(
    "",
    response_model=InboxItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_item(
    project_id: uuid.UUID,
    payload: CreateInboxItemRequest,
    user: CurrentUser,
    db: DbSession,
) -> InboxItemResponse:
    item = await ResearchInboxService(db).create_item(user, project_id, payload)
    return InboxItemResponse.model_validate(item)


@router.post(
    "/{item_id}/analyze",
    response_model=AnalyzeInboxItemResponse,
    dependencies=[Depends(require_csrf)],
)
async def analyze_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: AnalyzeInboxItemRequest,
    user: CurrentUser,
    db: DbSession,
) -> AnalyzeInboxItemResponse:
    run = await ResearchInboxService(db).analyze(
        user,
        project_id,
        item_id,
        payload.mode,
    )
    return AnalyzeInboxItemResponse(
        item_id=item_id,
        agent_run_id=run.id,
        status=run.status.value,
    )
