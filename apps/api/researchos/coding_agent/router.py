"""Coding agent run endpoint.

Reuses the agents runtime (agent_type=coding). The run proposes a pending patch;
it never writes files.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

router = APIRouter(prefix="/projects/{project_id}/coding-agent", tags=["coding-agent"])


class CodingAgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


@router.post(
    "/runs",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_coding_run(
    project_id: uuid.UUID, payload: CodingAgentRunRequest, user: CurrentUser, db: DbSession
) -> CreateAgentRunResponse:
    run = await AgentRunService(db).create_run(
        user, project_id, agent_type=AgentType.CODING, message=payload.message, context={}
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id, status=run.status, stream=f"/ws?project_id={project_id}"
    )
