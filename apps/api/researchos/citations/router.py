"""Mission citation organizer endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import CitationAuditResponse
from .service import CitationAuditService

router = APIRouter(
    prefix="/projects/{project_id}/missions/{mission_id}/citation-audits",
    tags=["mission-citations"],
)


@router.post(
    "",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def run_audit(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CreateAgentRunResponse:
    await CitationAuditService(db).validate_mission(user, project_id, mission_id, write=True)
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.CITATION_ORGANIZER,
        message="Audit mission citations, duplicates, missing metadata, keys, and BibTeX.",
        context={"mission_id": str(mission_id)},
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )


@router.get("", response_model=list[CitationAuditResponse])
async def list_audits(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[CitationAuditResponse]:
    items = await CitationAuditService(db).list_audits(user, project_id, mission_id)
    return [CitationAuditResponse.model_validate(item) for item in items]
