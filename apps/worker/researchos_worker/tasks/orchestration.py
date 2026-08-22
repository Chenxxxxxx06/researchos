"""Continuation task for the bounded autonomous research program."""

from __future__ import annotations

import uuid

import structlog
from researchos.common.asyncio_runner import run_async_task
from researchos.common.db import get_sessionmaker
from researchos.identity.repository import UserRepository
from researchos.orchestration.schemas import AutopilotStartRequest
from researchos.orchestration.service import OrchestrationService

from ..app import app

logger = structlog.get_logger(__name__)


async def _advance(
    project_id: str,
    mission_id: str,
    user_id: str,
    policy: dict,
) -> None:
    async with get_sessionmaker()() as db:
        actor = await UserRepository(db).get_by_id(uuid.UUID(user_id))
        if actor is None:
            logger.warning("autopilot_user_missing", user_id=user_id)
            return
        result = await OrchestrationService(db).autopilot_step(
            actor,
            uuid.UUID(project_id),
            uuid.UUID(mission_id),
            AutopilotStartRequest.model_validate(policy),
        )
        logger.info(
            "autopilot_step_finished",
            project_id=project_id,
            mission_id=mission_id,
            state=result.state,
            dispatched_task_id=str(result.dispatched_task_id or ""),
            blockers=result.blockers,
        )


@app.task(name="orchestration.advance")
def advance_autopilot(
    project_id: str,
    mission_id: str,
    user_id: str,
    policy: dict,
) -> str:
    run_async_task(lambda: _advance(project_id, mission_id, user_id, policy))
    return mission_id
