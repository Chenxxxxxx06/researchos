"""Git endpoints: status, log, commit diff, revert."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .repository_import import RepositorySnapshotService
from .schemas import (
    GitCommitDiff,
    GitLogResponse,
    GitRevertRequest,
    GitRevertResponse,
    GitStatusResponse,
    ImportRepositoryRequest,
    RepositorySnapshotResponse,
    StartRepositoryCodingResponse,
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


@router.get("/repository-snapshots", response_model=list[RepositorySnapshotResponse])
async def list_repository_snapshots(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    idea_id: uuid.UUID | None = Query(default=None),
) -> list[RepositorySnapshotResponse]:
    snapshots = await RepositorySnapshotService(db).list(user, project_id, idea_id=idea_id)
    return [RepositorySnapshotResponse.model_validate(item) for item in snapshots]


@router.post(
    "/repository-snapshots",
    response_model=RepositorySnapshotResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def import_repository_snapshot(
    project_id: uuid.UUID,
    payload: ImportRepositoryRequest,
    user: CurrentUser,
    db: DbSession,
) -> RepositorySnapshotResponse:
    snapshot = await RepositorySnapshotService(db).import_repository(
        user,
        project_id,
        idea_id=payload.idea_id,
        github_url=payload.github_url,
    )
    return RepositorySnapshotResponse.model_validate(snapshot)


@router.post(
    "/repository-snapshots/{snapshot_id}/start-coding",
    response_model=StartRepositoryCodingResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def start_repository_coding(
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> StartRepositoryCodingResponse:
    snapshot, session_id, run_id = await RepositorySnapshotService(db).start_coding(
        user, project_id, snapshot_id
    )
    return StartRepositoryCodingResponse(
        snapshot_id=snapshot.id,
        coding_session_id=session_id,
        coding_run_id=run_id,
        stream=f"/ws?project_id={project_id}",
    )
