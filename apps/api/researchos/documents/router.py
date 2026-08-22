"""LaTeX paper workspace endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from researchos.common.config import get_settings
from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.errors import NotFoundError
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .anchors import AnchorInsertService
from .bibtex import CitationService
from .enums import SuggestionStatus
from .models import DocumentSuggestion
from .schemas import (
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    CitationListResponse,
    CompileJobResponse,
    CreateLatexProjectRequest,
    DocumentFileResponse,
    DocumentFileSummary,
    FileRevisionSummary,
    InsertAnchorRequest,
    InsertAnchorResponse,
    InsertCitationRequest,
    InsertCitationResponse,
    LatexProjectResponse,
    SaveFileRequest,
    SelectionOpRequest,
    SelectionOpResponse,
    SuggestionResponse,
)
from .service import DocumentService
from .suggestions import SuggestionService, suggestion_range

router = APIRouter(prefix="/projects/{project_id}/latex-projects", tags=["paper"])


def _compile_response(job) -> CompileJobResponse:
    response = CompileJobResponse.model_validate(job)
    if job.pdf_path:
        response.pdf_url = (
            f"/projects/{job.project_id}/latex-projects/{job.latex_project_id}"
            f"/compile-jobs/{job.id}/pdf"
        )
    return response


def _suggestion_response(suggestion: DocumentSuggestion, path: str) -> SuggestionResponse:
    return SuggestionResponse(
        id=suggestion.id,
        path=path,
        op=suggestion.op,
        status=suggestion.status,
        base_version=suggestion.base_version,
        range=suggestion_range(suggestion),
        old_text=suggestion.old_text,
        new_text=suggestion.new_text,
        rationale=suggestion.rationale,
        spans=suggestion.spans_json or [],
        agent_run_id=suggestion.agent_run_id,
        last_error=suggestion.last_error,
        created_at=suggestion.created_at,
        resolved_at=suggestion.resolved_at,
    )


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
    lp = await DocumentService(db).create_latex_project(
        user,
        project_id,
        name=payload.name,
        template_id=payload.template_id,
    )
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


@router.get("/{latex_project_id}/files/history", response_model=list[FileRevisionSummary])
async def list_file_history(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    path: str = Query(...),
    limit: int = Query(default=20, ge=1, le=MAX_LIMIT),
) -> list[FileRevisionSummary]:
    revisions = await DocumentService(db).list_file_history(
        user, project_id, latex_project_id, path=path, limit=limit
    )
    return [FileRevisionSummary.model_validate(r) for r in revisions]


@router.get("/{latex_project_id}/files/revision", response_model=DocumentFileResponse)
async def get_file_revision(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    path: str = Query(...),
    version: int = Query(..., ge=1),
) -> DocumentFileResponse:
    file, revision = await DocumentService(db).get_file_revision(
        user, project_id, latex_project_id, path=path, version=version
    )
    return DocumentFileResponse(
        id=file.id,
        path=file.path,
        content=revision.content,
        version=revision.version,
        updated_at=revision.created_at,
    )


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
        user,
        project_id,
        latex_project_id,
        path=payload.path,
        content=payload.content,
        expected_version=payload.expected_version,
    )
    return DocumentFileResponse.model_validate(file)


# --- selection ops / suggestions ---------------------------------------------


@router.post(
    "/{latex_project_id}/selection-ops",
    response_model=SelectionOpResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
async def create_selection_op(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    payload: SelectionOpRequest,
    user: CurrentUser,
    db: DbSession,
) -> SelectionOpResponse:
    run = await SuggestionService(db).create_selection_op(
        user, project_id, latex_project_id, payload
    )
    return SelectionOpResponse(agent_run_id=run.id, stream=f"/ws?project_id={project_id}")


@router.get("/{latex_project_id}/suggestions", response_model=Page[SuggestionResponse])
async def list_suggestions(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    status_filter: SuggestionStatus | None = Query(default=None, alias="status"),
    path: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[SuggestionResponse]:
    rows, total = await SuggestionService(db).list_suggestions(
        user,
        project_id,
        latex_project_id,
        status=status_filter,
        path=path,
        limit=limit,
        offset=offset,
    )
    return Page[SuggestionResponse](
        items=[_suggestion_response(s, p) for s, p in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{latex_project_id}/suggestions/{suggestion_id}", response_model=SuggestionResponse
)
async def get_suggestion(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> SuggestionResponse:
    suggestion, path = await SuggestionService(db).get_suggestion(
        user, project_id, latex_project_id, suggestion_id
    )
    return _suggestion_response(suggestion, path)


@router.post(
    "/{latex_project_id}/suggestions/{suggestion_id}/accept",
    response_model=AcceptSuggestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def accept_suggestion(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: AcceptSuggestionRequest,
    user: CurrentUser,
    db: DbSession,
) -> AcceptSuggestionResponse:
    suggestion, file = await SuggestionService(db).accept(
        user,
        project_id,
        latex_project_id,
        suggestion_id,
        expected_version=payload.expected_version,
    )
    return AcceptSuggestionResponse(
        suggestion=_suggestion_response(suggestion, file.path),
        file=DocumentFileResponse.model_validate(file),
    )


@router.post(
    "/{latex_project_id}/suggestions/{suggestion_id}/reject",
    response_model=SuggestionResponse,
    dependencies=[Depends(require_csrf)],
)
async def reject_suggestion(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> SuggestionResponse:
    suggestion, path = await SuggestionService(db).reject(
        user, project_id, latex_project_id, suggestion_id
    )
    return _suggestion_response(suggestion, path)


# --- anchors -----------------------------------------------------------------


@router.post(
    "/{latex_project_id}/anchors/insert",
    response_model=InsertAnchorResponse,
    dependencies=[Depends(require_csrf)],
)
async def insert_anchor(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    payload: InsertAnchorRequest,
    user: CurrentUser,
    db: DbSession,
) -> InsertAnchorResponse:
    return await AnchorInsertService(db).insert(user, project_id, latex_project_id, payload)


# --- citations ---------------------------------------------------------------


@router.get("/{latex_project_id}/citations", response_model=CitationListResponse)
async def list_citations(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> CitationListResponse:
    items, total = await CitationService(db).list_citations(
        user, project_id, latex_project_id, limit=limit, offset=offset
    )
    return CitationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{latex_project_id}/citations/insert",
    response_model=InsertCitationResponse,
    dependencies=[Depends(require_csrf)],
)
async def insert_citation(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    payload: InsertCitationRequest,
    user: CurrentUser,
    db: DbSession,
) -> InsertCitationResponse:
    result = await CitationService(db).insert_citation(
        user,
        project_id,
        latex_project_id,
        paper_id=payload.paper_id,
        bib_path=payload.bib_path,
        expected_bib_version=payload.expected_bib_version,
        expected_main_version=payload.expected_main_version,
    )
    return InsertCitationResponse.model_validate(result)


# --- compile -----------------------------------------------------------------


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
    return _compile_response(job)


@router.get("/{latex_project_id}/compile-jobs/{job_id}", response_model=CompileJobResponse)
async def get_compile_job(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> CompileJobResponse:
    job = await DocumentService(db).get_compile_job(user, project_id, latex_project_id, job_id)
    return _compile_response(job)


@router.get("/{latex_project_id}/compile-jobs/{job_id}/pdf", response_class=FileResponse)
async def get_compile_pdf(
    project_id: uuid.UUID,
    latex_project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> FileResponse:
    job = await DocumentService(db).get_compile_job(user, project_id, latex_project_id, job_id)
    if not job.pdf_path:
        raise NotFoundError("Compiled PDF is not available.")
    root = Path(get_settings().artifact_root).resolve()
    path = Path(job.pdf_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise NotFoundError("Compiled PDF is not available.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{latex_project_id}-{job.id}.pdf",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
