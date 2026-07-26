"""Git endpoints: status, log, commit diff, revert."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    GitCommitDiff,
    GitLogResponse,
    GitRevertRequest,
    GitRevertResponse,
    GitStatusResponse,
)
from .service import GitService

router = APIRouter(prefix="/projects/{project_id}/git", tags=["git"])


@router.get("/status", response_model=GitStatusResponse)
async def git_status(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GitStatusResponse:
    return await GitService(db).status(user, project_id)


@router.get("/log", response_model=GitLogResponse)
async def git_log(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    path: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
) -> GitLogResponse:
    entries = await GitService(db).log(user, project_id, path=path, limit=limit, skip=skip)
    return GitLogResponse(entries=entries)


@router.get("/commits/{sha}/diff", response_model=GitCommitDiff)
async def git_commit_diff(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    sha: str = Path(pattern=r"^[0-9a-f]{7,64}$"),
) -> GitCommitDiff:
    return await GitService(db).commit_diff(user, project_id, sha)


@router.post(
    "/revert",
    response_model=GitRevertResponse,
    dependencies=[Depends(require_csrf)],
)
async def git_revert(
    project_id: uuid.UUID, payload: GitRevertRequest, user: CurrentUser, db: DbSession
) -> GitRevertResponse:
    return await GitService(db).revert(user, project_id, payload.sha)
