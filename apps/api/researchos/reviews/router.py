"""Structured literature review endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    GenerateReviewOutlineRequest,
    GenerateReviewSectionRequest,
    ReviewDocumentResponse,
    ReviewSectionResponse,
    ReviewVersionResponse,
    UpdateReviewSectionRequest,
)
from .service import ReviewService, review_metrics

router = APIRouter(
    prefix="/projects/{project_id}/missions/{mission_id}/review", tags=["mission-review"]
)


def _response(review, sections) -> ReviewDocumentResponse:
    coverage, unsupported = review_metrics(sections)
    return ReviewDocumentResponse(
        id=review.id,
        project_id=review.project_id,
        mission_id=review.mission_id,
        title=review.title,
        status=review.status,
        version=review.version,
        citation_coverage=coverage,
        unsupported_claims=unsupported,
        sections=[ReviewSectionResponse.model_validate(section) for section in sections],
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.get("", response_model=ReviewDocumentResponse)
async def get_review(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ReviewDocumentResponse:
    return _response(*await ReviewService(db).get(user, project_id, mission_id))


@router.post(
    "/outline", response_model=ReviewDocumentResponse, dependencies=[Depends(require_csrf)]
)
async def generate_outline(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: GenerateReviewOutlineRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReviewDocumentResponse:
    return _response(
        *await ReviewService(db).generate_outline(user, project_id, mission_id, payload)
    )


@router.put(
    "/sections/{section_id}",
    response_model=ReviewDocumentResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_section(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    section_id: uuid.UUID,
    payload: UpdateReviewSectionRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReviewDocumentResponse:
    return _response(
        *await ReviewService(db).update_section(user, project_id, mission_id, section_id, payload)
    )


@router.post(
    "/sections/{section_id}/generate",
    response_model=CreateAgentRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def generate_section(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    section_id: uuid.UUID,
    payload: GenerateReviewSectionRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateAgentRunResponse:
    section = await ReviewService(db).validate_section_generation(
        user, project_id, mission_id, section_id, payload
    )
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.REVIEW_SECTION,
        message="Draft one literature-review section from mission-scoped evidence.",
        context={
            "mission_id": str(mission_id),
            "section_id": str(section.id),
            "expected_version": payload.expected_version,
        },
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )


@router.get("/versions", response_model=list[ReviewVersionResponse])
async def list_versions(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ReviewVersionResponse]:
    versions = await ReviewService(db).versions(user, project_id, mission_id)
    return [ReviewVersionResponse.model_validate(version) for version in versions]
