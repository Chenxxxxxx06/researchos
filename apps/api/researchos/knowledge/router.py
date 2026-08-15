"""Mission knowledge, reading card, note, clustering, and retrieval endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    AddMissionPapersRequest,
    GenerateReadingCardRequest,
    MissionPaperResponse,
    RagSearchRequest,
    RagSearchResponse,
    ReadingCardResponse,
    ReadingCardUpsertRequest,
    ReadingCardVersionResponse,
    ReadingNoteCreateRequest,
    ReadingNoteResponse,
    ReadingNoteUpdateRequest,
    TopicClusterResponse,
    UpdateTopicClusterRequest,
)
from .service import KnowledgeService

router = APIRouter(prefix="/projects/{project_id}", tags=["research-knowledge"])


@router.post(
    "/missions/{mission_id}/papers",
    response_model=list[MissionPaperResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def add_mission_papers(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: AddMissionPapersRequest,
    user: CurrentUser,
    db: DbSession,
) -> list[MissionPaperResponse]:
    return await KnowledgeService(db).add_papers(user, project_id, mission_id, payload)


@router.get("/missions/{mission_id}/papers", response_model=list[MissionPaperResponse])
async def list_mission_papers(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[MissionPaperResponse]:
    return await KnowledgeService(db).list_papers(user, project_id, mission_id)


def _cluster_response(item) -> TopicClusterResponse:
    cluster, count = item
    data = TopicClusterResponse.model_validate(cluster).model_dump()
    data["paper_count"] = count
    return TopicClusterResponse(**data)


@router.post(
    "/missions/{mission_id}/cluster",
    response_model=list[TopicClusterResponse],
    dependencies=[Depends(require_csrf)],
)
async def cluster_mission_papers(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[TopicClusterResponse]:
    return [
        _cluster_response(item)
        for item in await KnowledgeService(db).cluster(user, project_id, mission_id)
    ]


@router.get("/missions/{mission_id}/clusters", response_model=list[TopicClusterResponse])
async def list_mission_clusters(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[TopicClusterResponse]:
    return [
        _cluster_response(item)
        for item in await KnowledgeService(db).list_clusters(user, project_id, mission_id)
    ]


@router.patch(
    "/missions/{mission_id}/clusters/{cluster_id}",
    response_model=TopicClusterResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_mission_cluster(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    cluster_id: uuid.UUID,
    payload: UpdateTopicClusterRequest,
    user: CurrentUser,
    db: DbSession,
) -> TopicClusterResponse:
    cluster = await KnowledgeService(db).update_cluster(
        user, project_id, mission_id, cluster_id, payload
    )
    return TopicClusterResponse.model_validate(cluster)


@router.post("/rag/search", response_model=RagSearchResponse, dependencies=[Depends(require_csrf)])
async def rag_search(
    project_id: uuid.UUID, payload: RagSearchRequest, user: CurrentUser, db: DbSession
) -> RagSearchResponse:
    return await KnowledgeService(db).rag_search(user, project_id, payload)


@router.put(
    "/papers/{paper_id}/reading-card",
    response_model=ReadingCardResponse,
    dependencies=[Depends(require_csrf)],
)
async def upsert_reading_card(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    payload: ReadingCardUpsertRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReadingCardResponse:
    card = await KnowledgeService(db).upsert_card(user, project_id, paper_id, payload)
    return ReadingCardResponse.model_validate(card)


@router.post(
    "/papers/{paper_id}/reading-card/generate",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def generate_reading_card(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    payload: GenerateReadingCardRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateAgentRunResponse:
    await KnowledgeService(db).validate_card_generation(
        user,
        project_id,
        paper_id,
        payload.mission_id,
        regenerate=payload.regenerate,
    )
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.READING_CARD,
        message="Generate a structured, section-grounded reading card for human review.",
        context={
            "mission_id": str(payload.mission_id),
            "paper_id": str(paper_id),
            "section_kinds": [kind.value for kind in payload.section_kinds],
        },
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )


@router.get("/missions/{mission_id}/reading-cards", response_model=list[ReadingCardResponse])
async def list_reading_cards(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ReadingCardResponse]:
    cards = await KnowledgeService(db).list_cards(user, project_id, mission_id)
    return [ReadingCardResponse.model_validate(card) for card in cards]


@router.get(
    "/papers/{paper_id}/reading-card/versions",
    response_model=list[ReadingCardVersionResponse],
)
async def list_reading_card_versions(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    mission_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[ReadingCardVersionResponse]:
    versions = await KnowledgeService(db).list_card_versions(user, project_id, paper_id, mission_id)
    return [ReadingCardVersionResponse.model_validate(version) for version in versions]


@router.post(
    "/papers/{paper_id}/notes",
    response_model=ReadingNoteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_reading_note(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    payload: ReadingNoteCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReadingNoteResponse:
    note = await KnowledgeService(db).create_note(user, project_id, paper_id, payload)
    return ReadingNoteResponse.model_validate(note)


@router.get("/papers/{paper_id}/notes", response_model=list[ReadingNoteResponse])
async def list_reading_notes(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    mission_id: uuid.UUID | None = Query(default=None),
) -> list[ReadingNoteResponse]:
    notes = await KnowledgeService(db).list_notes(user, project_id, paper_id, mission_id)
    return [ReadingNoteResponse.model_validate(note) for note in notes]


@router.patch(
    "/notes/{note_id}", response_model=ReadingNoteResponse, dependencies=[Depends(require_csrf)]
)
async def update_reading_note(
    project_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: ReadingNoteUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReadingNoteResponse:
    note = await KnowledgeService(db).update_note(user, project_id, note_id, payload)
    return ReadingNoteResponse.model_validate(note)


@router.delete(
    "/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
async def delete_reading_note(
    project_id: uuid.UUID, note_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await KnowledgeService(db).delete_note(user, project_id, note_id)
