"""LaTeX paper workspace endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    CompileJobResponse,
    CreateLatexProjectRequest,
    DocumentFileResponse,
    DocumentFileSummary,
    LatexProjectResponse,
    SaveFileRequest,
)
from .service import DocumentService

router = APIRouter(prefix="/projects/{project_id}/latex-projects", tags=["paper"])


@router.get("", response_model=list[LatexProjectResponse])
async def list_latex_projects(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[LatexProjectResponse]:
    items = await DocumentService(db).list_latex_projects(user, project_id)
    return [LatexProjectResponse.model_validate(p) for p in items]


@router.post(
    "",
    response_model=LatexProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_latex_project(
    project_id: uuid.UUID, payload: CreateLatexProjectRequest, user: CurrentUser, db: DbSession
) -> LatexProjectResponse:
    lp = await DocumentService(db).create_latex_project(user, project_id, name=payload.name)
    return LatexProjectResponse.model_validate(lp)


@router.get("/{latex_project_id}", response_model=LatexProjectResponse)
async def get_latex_project(
    project_id: uuid.UUID, latex_project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> LatexProjectResponse:
    lp = await DocumentService(db).get_latex_project(user, project_id, latex_project_id)
    return LatexProjectResponse.model_validate(lp)


@router.get("/{latex_project_id}/files", response_model=list[DocumentFileSummary])
async def list_files(
    project_id: uuid.UUID, latex_project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[DocumentFileSummary]:
    files = await DocumentService(db).list_files(user, project_id, latex_project_id)
    return [DocumentFileSummary.model_validate(f) for f in files]


@router.get("/{latex_project_id}/files/content", response_model=DocumentFileResponse)
async def get_file(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    path: str = Query(...),
) -> DocumentFileResponse:
    file = await DocumentService(db).get_file(user, project_id, latex_project_id, path)
    return DocumentFileResponse.model_validate(file)


@router.put(
    "/{latex_project_id}/files",
    response_model=DocumentFileResponse,
    dependencies=[Depends(require_csrf)],
)
async def save_file(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    payload: SaveFileRequest,
    user: CurrentUser,
    db: DbSession,
) -> DocumentFileResponse:
    file = await DocumentService(db).save_file(
        user, project_id, latex_project_id, path=payload.path, content=payload.content
    )
    return DocumentFileResponse.model_validate(file)


@router.post(
    "/{latex_project_id}/compile",
    response_model=CompileJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def compile_latex(
    project_id: uuid.UUID, latex_project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CompileJobResponse:
    job = await DocumentService(db).compile(user, project_id, latex_project_id)
    return CompileJobResponse.model_validate(job)


@router.get("/{latex_project_id}/compile-jobs/{job_id}", response_model=CompileJobResponse)
async def get_compile_job(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> CompileJobResponse:
    job = await DocumentService(db).get_compile_job(user, project_id, latex_project_id, job_id)
    return CompileJobResponse.model_validate(job)
