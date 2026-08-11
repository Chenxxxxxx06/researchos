"""Host-key verified SSH workspace endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    FileContentResponse,
    SSHFileSaveRequest,
    SSHProfileResponse,
    SSHProfileUpsert,
    SSHRunRequest,
    SSHTestResponse,
    SSHTreeResponse,
    TerminalRunResponse,
)
from .service import SSHService

router = APIRouter(prefix="/projects/{project_id}/workspace/ssh", tags=["workspace-ssh"])


@router.get("/profiles", response_model=list[SSHProfileResponse])
async def list_profiles(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[SSHProfileResponse]:
    return await SSHService(db).list_profiles(user, project_id)


@router.put(
    "/profiles",
    response_model=SSHProfileResponse,
    dependencies=[Depends(require_csrf)],
)
async def save_profile(
    project_id: uuid.UUID,
    payload: SSHProfileUpsert,
    user: CurrentUser,
    db: DbSession,
) -> SSHProfileResponse:
    return await SSHService(db).save_profile(user, project_id, payload)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_profile(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    await SSHService(db).delete_profile(user, project_id, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/profiles/{profile_id}/test",
    response_model=SSHTestResponse,
    dependencies=[Depends(require_csrf)],
)
async def test_profile(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> SSHTestResponse:
    return SSHTestResponse.model_validate(await SSHService(db).test(user, project_id, profile_id))


@router.get("/profiles/{profile_id}/tree", response_model=SSHTreeResponse)
async def tree(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> SSHTreeResponse:
    return SSHTreeResponse.model_validate(await SSHService(db).tree(user, project_id, profile_id))


@router.get("/profiles/{profile_id}/files", response_model=FileContentResponse)
async def read_file(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    path: Annotated[str, Query(min_length=1, max_length=1024)],
) -> FileContentResponse:
    return FileContentResponse.model_validate(
        await SSHService(db).read(user, project_id, profile_id, path)
    )


@router.put(
    "/profiles/{profile_id}/files",
    response_model=FileContentResponse,
    dependencies=[Depends(require_csrf)],
)
async def save_file(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SSHFileSaveRequest,
    user: CurrentUser,
    db: DbSession,
) -> FileContentResponse:
    return FileContentResponse.model_validate(
        await SSHService(db).write(
            user,
            project_id,
            profile_id,
            path=payload.path,
            content=payload.content,
            base_sha=payload.base_sha,
        )
    )


@router.post(
    "/profiles/{profile_id}/terminal/run",
    response_model=TerminalRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def run_terminal(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SSHRunRequest,
    user: CurrentUser,
    db: DbSession,
) -> TerminalRunResponse:
    return TerminalRunResponse.model_validate(
        await SSHService(db).execute(
            user,
            project_id,
            profile_id,
            argv=payload.argv,
            cwd=payload.cwd,
            timeout_seconds=payload.timeout_seconds,
        )
    )
