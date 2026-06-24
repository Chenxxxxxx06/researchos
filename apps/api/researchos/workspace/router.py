"""Workspace endpoints: file tree and file read."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from researchos.common.deps import CurrentUser, DbSession

from .schemas import FileContentResponse, TreeResponse
from .service import WorkspaceService

router = APIRouter(prefix="/projects/{project_id}/workspace", tags=["workspace"])


@router.get("/tree", response_model=TreeResponse)
async def get_tree(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TreeResponse:
    return await WorkspaceService(db).get_tree(user, project_id)


@router.get("/files", response_model=FileContentResponse)
async def get_file(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession, path: str = Query(...)
) -> FileContentResponse:
    return await WorkspaceService(db).read_file(user, project_id, path)
