"""Workspace endpoints: file tree, file read, and grep."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, Query

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.errors import ValidationError

from .schemas import (
    FileContentResponse,
    GrepMatch,
    GrepResponse,
    SaveFileRequest,
    TerminalRunRequest,
    TerminalRunResponse,
    TreeResponse,
)
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


@router.put(
    "/files",
    response_model=FileContentResponse,
    dependencies=[Depends(require_csrf)],
)
async def save_file(
    project_id: uuid.UUID,
    payload: SaveFileRequest,
    user: CurrentUser,
    db: DbSession,
) -> FileContentResponse:
    return await WorkspaceService(db).save_file(
        user,
        project_id,
        path=payload.path,
        content=payload.content,
        base_sha=payload.base_sha,
    )


@router.post(
    "/terminal/run",
    response_model=TerminalRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def run_terminal(
    project_id: uuid.UUID,
    payload: TerminalRunRequest,
    user: CurrentUser,
    db: DbSession,
) -> TerminalRunResponse:
    return await WorkspaceService(db).run_terminal(
        user,
        project_id,
        argv=payload.argv,
        cwd=payload.cwd,
        timeout_seconds=payload.timeout_seconds,
    )


@router.get("/grep", response_model=GrepResponse)
async def grep_workspace(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    query: str = Query(min_length=1),
    regex: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=100),
) -> GrepResponse:
    pattern = query if regex else re.escape(query)
    try:
        data = await WorkspaceService(db).grep(
            user, project_id, pattern=pattern, max_results=limit
        )
    except re.error as exc:
        raise ValidationError(
            f"Invalid regular expression: {exc}", http_status=400
        ) from exc
    return GrepResponse(
        matches=[
            GrepMatch(path=m["path"], line=m["line_no"], preview=m["line"])
            for m in data["matches"]
        ],
        truncated=data["truncated"],
    )
