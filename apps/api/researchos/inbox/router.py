"""Project-scoped Research Inbox endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.roles import ProjectRole

from .extraction import extract_upload
from .schemas import (
    AnalyzeInboxItemRequest,
    AnalyzeInboxItemResponse,
    CreateInboxItemRequest,
    InboxAnalysisMode,
    InboxItemResponse,
    UploadInboxItemResponse,
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
    "/upload",
    response_model=UploadInboxItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_item(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    sender: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    analysis_mode: Annotated[InboxAnalysisMode, Form()] = "direction",
    auto_analyze: Annotated[bool, Form()] = True,
) -> UploadInboxItemResponse:
    service = ResearchInboxService(db)
    await service.projects.ensure_access(user, project_id, ProjectRole.RESEARCHER)
    text, source_type = await extract_upload(db, project_id, file)
    filename = file.filename or "upload"
    item = await service.create_item(
        user,
        project_id,
        CreateInboxItemRequest(
            source_type=source_type,
            sender=sender,
            title=(title or filename).strip(),
            content_text=text,
            original_filename=filename,
            media_type=file.content_type,
        ),
    )
    analysis = None
    if auto_analyze:
        run = await service.analyze(user, project_id, item.id, analysis_mode)
        analysis = AnalyzeInboxItemResponse(
            item_id=item.id,
            agent_run_id=run.id,
            status=run.status.value,
        )
        await db.refresh(item)
    return UploadInboxItemResponse(
        item=InboxItemResponse.model_validate(item),
        analysis=analysis,
    )


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
