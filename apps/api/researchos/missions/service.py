"""Research Mission state machine and authorization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .enums import (
    MISSION_STEP_ORDER,
    MissionStatus,
    MissionStepKind,
    MissionStepStatus,
)
from .models import MissionEvent, MissionStep, ResearchMission
from .repository import MissionRepository
from .schemas import CreateMissionRequest, UpdateMissionRequest, UpdateMissionStepRequest


def _now() -> datetime:
    return datetime.now(tz=UTC)


class MissionVersionConflict(ConflictError):
    code = "mission_version_conflict"
    message = "The mission changed since it was loaded. Refresh and try again."


class MissionStepVersionConflict(ConflictError):
    code = "mission_step_version_conflict"
    message = "The mission step changed since it was loaded. Refresh and try again."


class MissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)
        self.repo = MissionRepository(db)

    def _event(
        self,
        mission: ResearchMission,
        actor: User,
        event_type: str,
        summary: str,
        *,
        step_kind: MissionStepKind | None = None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            MissionEvent(
                mission_id=mission.id,
                project_id=mission.project_id,
                event_type=event_type,
                summary=summary,
                step_kind=step_kind,
                payload_json=payload or {},
                actor_id=actor.id,
            )
        )

    async def _load(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        min_role: ProjectRole,
    ) -> ResearchMission:
        await self.projects.ensure_access(actor, project_id, min_role)
        mission = await self.repo.get(project_id, mission_id)
        if mission is None:
            raise NotFoundError("Research mission not found.")
        return mission

    async def create(
        self, actor: User, project_id: uuid.UUID, payload: CreateMissionRequest
    ) -> tuple[ResearchMission, list[MissionStep]]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        now = _now()
        mission = ResearchMission(
            project_id=project_id,
            topic=payload.topic,
            objective=payload.objective,
            field=payload.field,
            scope_json=payload.scope,
            status=MissionStatus.DRAFT,
            current_step=MissionStepKind.SCOPE,
            progress=0.0,
            version=1,
            last_activity_at=now,
            created_by=actor.id,
            updated_by=actor.id,
        )
        self.db.add(mission)
        await self.db.flush()
        steps = [
            MissionStep(
                mission_id=mission.id,
                project_id=project_id,
                step_kind=kind,
                position=index,
                status=(
                    MissionStepStatus.READY
                    if index == 0
                    else MissionStepStatus.LOCKED
                ),
                input_json=payload.scope if kind is MissionStepKind.SCOPE else {},
                output_json={},
                version=1,
            )
            for index, kind in enumerate(MISSION_STEP_ORDER)
        ]
        self.db.add_all(steps)
        self._event(
            mission,
            actor,
            "mission.created",
            f"创建科研任务：{mission.topic}",
            step_kind=MissionStepKind.SCOPE,
        )
        await self.db.commit()
        await self.db.refresh(mission)
        for step in steps:
            await self.db.refresh(step)
        return mission, steps

    async def list_missions(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        status: MissionStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ResearchMission], int]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.repo.list_missions(
            project_id, status=status, limit=limit, offset=offset
        )

    async def get(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> tuple[ResearchMission, list[MissionStep]]:
        mission = await self._load(
            actor, project_id, mission_id, ProjectRole.VIEWER
        )
        return mission, await self.repo.steps(mission.id)

    async def update(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: UpdateMissionRequest,
    ) -> tuple[ResearchMission, list[MissionStep]]:
        mission = await self._load(
            actor, project_id, mission_id, ProjectRole.RESEARCHER
        )
        if mission.version != payload.expected_version:
            raise MissionVersionConflict(details={"current_version": mission.version})
        changed: list[str] = []
        if payload.topic is not None and payload.topic != mission.topic:
            mission.topic = payload.topic
            changed.append("topic")
        if payload.objective is not None and payload.objective != mission.objective:
            mission.objective = payload.objective
            changed.append("objective")
        if payload.field is not None and payload.field != mission.field:
            mission.field = payload.field or None
            changed.append("field")
        if payload.scope is not None and payload.scope != mission.scope_json:
            mission.scope_json = payload.scope
            scope_step = await self.repo.step(mission.id, MissionStepKind.SCOPE)
            if scope_step is not None:
                scope_step.input_json = payload.scope
                scope_step.version += 1
            changed.append("scope")
        if payload.status is not None and payload.status != mission.status:
            allowed = {
                MissionStatus.DRAFT: {MissionStatus.ACTIVE, MissionStatus.ARCHIVED},
                MissionStatus.ACTIVE: {MissionStatus.PAUSED, MissionStatus.ARCHIVED},
                MissionStatus.PAUSED: {MissionStatus.ACTIVE, MissionStatus.ARCHIVED},
                MissionStatus.COMPLETED: {MissionStatus.ARCHIVED},
                MissionStatus.ARCHIVED: set(),
            }[mission.status]
            if payload.status not in allowed:
                raise ValidationError(
                    f"Cannot change mission status from {mission.status} to {payload.status}."
                )
            mission.status = payload.status
            changed.append("status")
        if changed:
            mission.version += 1
            mission.updated_by = actor.id
            mission.last_activity_at = _now()
            self._event(
                mission,
                actor,
                "mission.updated",
                "更新科研任务：" + "、".join(changed),
                step_kind=mission.current_step,
                payload={"changed": changed},
            )
            await self.db.commit()
            await self.db.refresh(mission)
        return mission, await self.repo.steps(mission.id)

    async def update_step(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        step_kind: MissionStepKind,
        payload: UpdateMissionStepRequest,
    ) -> tuple[ResearchMission, list[MissionStep]]:
        mission = await self._load(
            actor, project_id, mission_id, ProjectRole.RESEARCHER
        )
        if mission.status in {MissionStatus.COMPLETED, MissionStatus.ARCHIVED}:
            raise ValidationError("Completed or archived missions cannot be edited.")
        step = await self.repo.step(mission.id, step_kind)
        if step is None:
            raise NotFoundError("Mission step not found.")
        if step.version != payload.expected_version:
            raise MissionStepVersionConflict(details={"current_version": step.version})
        if step.status is MissionStepStatus.LOCKED:
            raise ValidationError("Complete the preceding mission step first.")
        if step.status is MissionStepStatus.COMPLETED:
            raise ValidationError("Approved mission steps cannot be edited.")
        if step_kind is not mission.current_step:
            raise ValidationError("Only the current mission step can be edited.")

        now = _now()
        if step.started_at is None:
            step.started_at = now
        if payload.input is not None:
            step.input_json = payload.input
        if payload.output is not None:
            step.output_json = payload.output
        if payload.status is not None:
            if payload.status not in {
                MissionStepStatus.IN_PROGRESS,
                MissionStepStatus.NEEDS_REVIEW,
            }:
                raise ValidationError(
                    "A step can only be marked in_progress or needs_review before approval."
                )
            step.status = payload.status
        elif step.status is MissionStepStatus.READY:
            step.status = MissionStepStatus.IN_PROGRESS
        step.version += 1
        mission.status = MissionStatus.ACTIVE
        mission.version += 1
        mission.updated_by = actor.id
        mission.last_activity_at = now
        self._event(
            mission,
            actor,
            "mission.step.updated",
            f"更新步骤：{step_kind.value}",
            step_kind=step_kind,
            payload={"step_version": step.version, "status": step.status.value},
        )
        await self.db.commit()
        await self.db.refresh(mission)
        return mission, await self.repo.steps(mission.id)

    async def approve_step(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        step_kind: MissionStepKind,
        *,
        expected_version: int,
        note: str | None,
    ) -> tuple[ResearchMission, list[MissionStep]]:
        mission = await self._load(
            actor, project_id, mission_id, ProjectRole.RESEARCHER
        )
        if mission.status is MissionStatus.ARCHIVED:
            raise ValidationError("Archived missions cannot be approved.")
        step = await self.repo.step(mission.id, step_kind)
        if step is None:
            raise NotFoundError("Mission step not found.")
        if step.version != expected_version:
            raise MissionStepVersionConflict(details={"current_version": step.version})
        if step_kind is not mission.current_step:
            raise ValidationError("Only the current mission step can be approved.")
        if step.status in {MissionStepStatus.LOCKED, MissionStepStatus.COMPLETED}:
            raise ValidationError("This mission step cannot be approved.")

        now = _now()
        step.status = MissionStepStatus.COMPLETED
        step.completed_at = now
        step.approved_at = now
        step.approved_by = actor.id
        step.version += 1

        index = MISSION_STEP_ORDER.index(step_kind)
        completed_count = index + 1
        mission.progress = completed_count / len(MISSION_STEP_ORDER) * 100.0
        if index == len(MISSION_STEP_ORDER) - 1:
            mission.status = MissionStatus.COMPLETED
            mission.current_step = step_kind
            summary = "科研任务全部步骤已完成"
        else:
            next_kind = MISSION_STEP_ORDER[index + 1]
            next_step = await self.repo.step(mission.id, next_kind)
            if next_step is None:
                raise NotFoundError("Next mission step not found.")
            next_step.status = MissionStepStatus.READY
            next_step.version += 1
            mission.current_step = next_kind
            mission.status = MissionStatus.ACTIVE
            summary = f"批准 {step_kind.value}，已解锁 {next_kind.value}"
        mission.version += 1
        mission.updated_by = actor.id
        mission.last_activity_at = now
        self._event(
            mission,
            actor,
            "mission.step.approved",
            summary,
            step_kind=step_kind,
            payload={"note": note or "", "progress": mission.progress},
        )
        await self.db.commit()
        await self.db.refresh(mission)
        return mission, await self.repo.steps(mission.id)

    async def timeline(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[MissionEvent], int]:
        mission = await self._load(
            actor, project_id, mission_id, ProjectRole.VIEWER
        )
        return await self.repo.events(mission.id, limit=limit, offset=offset)
