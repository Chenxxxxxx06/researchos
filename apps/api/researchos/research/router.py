"""Research endpoints: papers, ideas, critiques."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .schemas import (
    CreateIdeaRequest,
    CritiqueResponse,
    IdeaResponse,
    ImportPapersRequest,
    PaperResponse,
    PaperSearchRequest,
    PaperSearchResponse,
    UpdateIdeaRequest,
)
from .service import CritiqueService, IdeaService, PaperService

router = APIRouter(prefix="/projects/{project_id}", tags=["research"])


# --- Papers ------------------------------------------------------------------
@router.post(
    "/papers/search",
    response_model=PaperSearchResponse,
    dependencies=[Depends(require_csrf)],
)
async def search_papers(
    project_id: uuid.UUID, payload: PaperSearchRequest, user: CurrentUser, db: DbSession
) -> PaperSearchResponse:
    results = await PaperService(db).search(
        user, project_id, query=payload.query, limit=payload.limit
    )
    return PaperSearchResponse(results=results)


@router.post(
    "/papers/import",
    response_model=list[PaperResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def import_papers(
    project_id: uuid.UUID, payload: ImportPapersRequest, user: CurrentUser, db: DbSession
) -> list[PaperResponse]:
    papers = await PaperService(db).import_papers(user, project_id, payload.papers)
    return [PaperResponse.model_validate(p) for p in papers]


@router.get("/papers", response_model=Page[PaperResponse])
async def list_papers(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[PaperResponse]:
    page = await PaperService(db).list_library(user, project_id, limit=limit, offset=offset)
    return Page[PaperResponse](
        items=[PaperResponse.model_validate(p) for p in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/papers/{paper_id}", response_model=PaperResponse)
async def get_paper(
    project_id: uuid.UUID, paper_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> PaperResponse:
    paper = await PaperService(db).get(user, project_id, paper_id)
    return PaperResponse.model_validate(paper)


@router.delete(
    "/papers/{paper_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_paper(
    project_id: uuid.UUID, paper_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await PaperService(db).delete(user, project_id, paper_id)


# --- Ideas -------------------------------------------------------------------
@router.post(
    "/ideas",
    response_model=IdeaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_idea(
    project_id: uuid.UUID, payload: CreateIdeaRequest, user: CurrentUser, db: DbSession
) -> IdeaResponse:
    idea = await IdeaService(db).create(
        user,
        project_id,
        title=payload.title,
        description=payload.description,
        hypothesis=payload.hypothesis,
    )
    return IdeaResponse.model_validate(idea)


@router.get("/ideas", response_model=Page[IdeaResponse])
async def list_ideas(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[IdeaResponse]:
    page = await IdeaService(db).list(user, project_id, limit=limit, offset=offset)
    return Page[IdeaResponse](
        items=[IdeaResponse.model_validate(i) for i in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/ideas/{idea_id}", response_model=IdeaResponse)
async def get_idea(
    project_id: uuid.UUID, idea_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> IdeaResponse:
    idea = await IdeaService(db).get(user, project_id, idea_id)
    return IdeaResponse.model_validate(idea)


@router.patch("/ideas/{idea_id}", response_model=IdeaResponse, dependencies=[Depends(require_csrf)])
async def update_idea(
    project_id: uuid.UUID,
    idea_id: uuid.UUID,
    payload: UpdateIdeaRequest,
    user: CurrentUser,
    db: DbSession,
) -> IdeaResponse:
    idea = await IdeaService(db).update(
        user,
        project_id,
        idea_id,
        title=payload.title,
        description=payload.description,
        hypothesis=payload.hypothesis,
        status=payload.status,
    )
    return IdeaResponse.model_validate(idea)


# --- Critic review -----------------------------------------------------------
@router.post(
    "/ideas/{idea_id}/critic-review",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def run_critic_review(
    project_id: uuid.UUID, idea_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CreateAgentRunResponse:
    # Ensure the idea exists and the caller has access before launching a run.
    idea = await IdeaService(db).get(user, project_id, idea_id)
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.CRITIC,
        message=f"Critique idea: {idea.title}",
        context={"idea_id": str(idea_id)},
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id, status=run.status, stream=f"/ws?project_id={project_id}"
    )


@router.get("/ideas/{idea_id}/critiques", response_model=list[CritiqueResponse])
async def list_critiques(
    project_id: uuid.UUID, idea_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[CritiqueResponse]:
    critiques = await CritiqueService(db).list_for_idea(user, project_id, idea_id)
    return [CritiqueResponse.model_validate(c) for c in critiques]
