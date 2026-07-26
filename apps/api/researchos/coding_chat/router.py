"""Coding chat endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .schemas import (
    ChatSessionDetailResponse,
    ChatSessionResponse,
    CreateChatMessageRequest,
    CreateChatMessageResponse,
    CreateChatSessionRequest,
)
from .service import CodingChatService

router = APIRouter(prefix="/projects/{project_id}/coding-chat", tags=["coding-chat"])


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_session(
    project_id: uuid.UUID, payload: CreateChatSessionRequest, user: CurrentUser, db: DbSession
) -> ChatSessionResponse:
    session = await CodingChatService(db).create_session(user, project_id, title=payload.title)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=Page[ChatSessionResponse])
async def list_sessions(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[ChatSessionResponse]:
    page = await CodingChatService(db).list_sessions(user, project_id, limit=limit, offset=offset)
    return Page[ChatSessionResponse](
        items=[ChatSessionResponse.model_validate(s) for s in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    project_id: uuid.UUID, session_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ChatSessionDetailResponse:
    session = await CodingChatService(db).get_session(user, project_id, session_id)
    return ChatSessionDetailResponse.model_validate(session)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=CreateChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def post_message(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: CreateChatMessageRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateChatMessageResponse:
    message, run = await CodingChatService(db).post_message(
        user, project_id, session_id, message=payload.message
    )
    return CreateChatMessageResponse(
        message_id=message.id,
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )
