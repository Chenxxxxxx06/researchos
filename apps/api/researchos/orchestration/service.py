"""Coordinator state machine for durable mission task DAGs."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.service import AgentRunService
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.git.models import RepositorySnapshot
from researchos.identity.models import User
from researchos.llm_config.models import LLMProviderConfig
from researchos.missions.enums import MissionStatus, MissionStepKind, MissionStepStatus
from researchos.missions.models import MissionStep, ResearchMission
from researchos.patches.enums import PatchStatus
from researchos.patches.models import PatchProposal
from researchos.projects.service import ProjectService
from researchos.research.enums import IdeaStatus
from researchos.research.models import Idea

from .enums import ApprovalGateStatus, MissionTaskStatus
from .models import (
    ApprovalGate,
    MissionTask,
    MissionTaskDependency,
    TaskArtifact,
    TaskEvent,
    TaskLease,
)
from .schemas import (
    ArtifactSubmission,
    CoordinatorTickResponse,
    DispatchTaskResponse,
    LeaseTaskResponse,
    MissionTaskResponse,
    OrchestrationGraphResponse,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _hash_payload(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_acyclic(keys: set[str], dependencies: list[tuple[str, str]]) -> None:
    """Reject missing nodes, self edges, and cycles before graph persistence."""

    incoming: dict[str, set[str]] = {key: set() for key in keys}
    outgoing: dict[str, set[str]] = {key: set() for key in keys}
    for task_key, dependency_key in dependencies:
        if task_key not in keys or dependency_key not in keys:
            raise ValidationError("Task dependency references an unknown task key.")
        if task_key == dependency_key:
            raise ValidationError("A task cannot depend on itself.")
        incoming[task_key].add(dependency_key)
        outgoing[dependency_key].add(task_key)
    ready = [key for key, parents in incoming.items() if not parents]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in outgoing[key]:
            incoming[child].discard(key)
            if not incoming[child]:
                ready.append(child)
    if visited != len(keys):
        raise ValidationError("Mission task dependencies must form an acyclic graph.")


_TASK_TEMPLATE: tuple[dict, ...] = (
    {"key": "scope", "title": "Approve research scope", "role": "coordinator", "stage": "scope"},
    {
        "key": "discover",
        "title": "Discover and ingest literature",
        "role": "evidence",
        "agent": "research",
        "stage": "literature",
    },
    {
        "key": "read",
        "title": "Build section-focused reading cards",
        "role": "reader",
        "agent": "reading_card",
        "stage": "reading",
    },
    {
        "key": "synthesize",
        "title": "Synthesize cross-paper evidence",
        "role": "synthesizer",
        "agent": "research",
        "stage": "reading",
    },
    {
        "key": "gap",
        "title": "Explore falsifiable research gaps",
        "role": "idea",
        "agent": "research",
        "stage": "review",
    },
    {
        "key": "critic",
        "title": "Critique novelty and feasibility",
        "role": "critic",
        "agent": "critic",
        "stage": "review",
    },
    {
        "key": "direction",
        "title": "Approve one research direction",
        "role": "coordinator",
        "stage": "review",
    },
    {
        "key": "repository",
        "title": "Import approved repository snapshot",
        "role": "repository_scout",
        "stage": "experiment_plan",
    },
    {
        "key": "baseline",
        "title": "Establish reproducible baseline",
        "role": "experiment_planner",
        "agent": "experiment_planner",
        "stage": "experiment_plan",
    },
    {
        "key": "coding",
        "title": "Propose implementation patch",
        "role": "coding",
        "agent": "coding",
        "stage": "experiment_plan",
    },
    {
        "key": "experiment_plan",
        "title": "Build experiment and ablation DAG",
        "role": "experiment_planner",
        "agent": "experiment_planner",
        "stage": "experiment_plan",
    },
    {
        "key": "experiment_run",
        "title": "Run approved experiment matrix",
        "role": "experiment_runner",
        "agent": "experiment",
        "stage": "experiment_plan",
    },
    {
        "key": "reproduce",
        "title": "Reproduce primary results",
        "role": "reproducibility",
        "agent": "experiment",
        "stage": "experiment_plan",
    },
    {
        "key": "analyze",
        "title": "Analyze results and negative evidence",
        "role": "analyst",
        "agent": "research",
        "stage": "experiment_plan",
    },
    {
        "key": "write",
        "title": "Write evidence-bound manuscript",
        "role": "writer",
        "agent": "latex",
        "stage": "review",
    },
    {
        "key": "review",
        "title": "Review claims and venue fit",
        "role": "reviewer",
        "agent": "research",
        "stage": "review",
    },
    {
        "key": "release",
        "title": "Approve release candidate",
        "role": "release",
        "agent": "coding",
        "stage": "review",
    },
)

_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("discover", "scope"),
    ("read", "discover"),
    ("synthesize", "read"),
    ("gap", "synthesize"),
    ("critic", "gap"),
    ("direction", "critic"),
    ("repository", "direction"),
    ("baseline", "repository"),
    ("coding", "repository"),
    ("experiment_plan", "baseline"),
    ("experiment_plan", "coding"),
    ("experiment_run", "experiment_plan"),
    ("reproduce", "experiment_run"),
    ("analyze", "reproduce"),
    ("write", "analyze"),
    ("review", "write"),
    ("release", "review"),
)

_GATES: tuple[tuple[str, str, str, bool], ...] = (
    ("scope", "scope", "before", True),
    ("direction", "direction", "before", True),
    ("repository", "repository_import", "before", True),
    ("coding", "patch_apply", "after", True),
    ("experiment_run", "compute", "before", False),
    ("release", "release", "after", True),
)


class OrchestrationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def _event(
        self,
        task: MissionTask,
        event_type: str,
        payload: dict,
        *,
        actor_id: uuid.UUID | None,
        message: str | None = None,
    ) -> None:
        current = await self.db.scalar(
            select(func.max(TaskEvent.seq)).where(TaskEvent.task_id == task.id)
        )
        self.db.add(
            TaskEvent(
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.id,
                seq=int(current) + 1 if current is not None else 0,
                event_type=event_type,
                payload_json=payload,
                actor_id=actor_id,
                message=message,
            )
        )

    async def _mission(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID, *, write: bool
    ) -> ResearchMission:
        await self.projects.ensure_access(
            actor, project_id, ProjectRole.RESEARCHER if write else ProjectRole.VIEWER
        )
        mission = await self.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != project_id:
            raise NotFoundError("Research mission not found.")
        return mission

    async def graph(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> OrchestrationGraphResponse:
        await self._mission(actor, project_id, mission_id, write=False)
        return await self._graph_unchecked(mission_id)

    async def _graph_unchecked(self, mission_id: uuid.UUID) -> OrchestrationGraphResponse:
        tasks = list(
            (
                await self.db.execute(
                    select(MissionTask)
                    .where(MissionTask.mission_id == mission_id)
                    .order_by(MissionTask.priority.asc(), MissionTask.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        task_ids = [task.id for task in tasks]
        if task_ids:
            dependencies = list(
                (
                    await self.db.execute(
                        select(MissionTaskDependency).where(
                            MissionTaskDependency.task_id.in_(task_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            artifacts = list(
                (
                    await self.db.execute(
                        select(TaskArtifact)
                        .where(TaskArtifact.task_id.in_(task_ids))
                        .order_by(TaskArtifact.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            gates = list(
                (
                    await self.db.execute(
                        select(ApprovalGate).where(ApprovalGate.task_id.in_(task_ids))
                    )
                )
                .scalars()
                .all()
            )
            events = list(
                (
                    await self.db.execute(
                        select(TaskEvent)
                        .where(TaskEvent.task_id.in_(task_ids))
                        .order_by(TaskEvent.created_at.desc())
                        .limit(200)
                    )
                )
                .scalars()
                .all()
            )
        else:
            dependencies, artifacts, gates, events = [], [], [], []
        return OrchestrationGraphResponse(
            mission_id=mission_id,
            tasks=tasks,
            dependencies=dependencies,
            artifacts=artifacts,
            gates=gates,
            events=events,
            counts=dict(Counter(task.status for task in tasks)),
        )

    async def bootstrap(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> OrchestrationGraphResponse:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        await self.db.execute(
            select(ResearchMission.id).where(ResearchMission.id == mission.id).with_for_update()
        )
        existing = await self.db.scalar(
            select(func.count())
            .select_from(MissionTask)
            .where(MissionTask.mission_id == mission.id)
        )
        if not existing:
            validate_acyclic({str(item["key"]) for item in _TASK_TEMPLATE}, list(_DEPENDENCIES))
            steps = {
                step.step_kind.value: step
                for step in (
                    (
                        await self.db.execute(
                            select(MissionStep).where(MissionStep.mission_id == mission.id)
                        )
                    )
                    .scalars()
                    .all()
                )
            }
            task_by_key: dict[str, MissionTask] = {}
            for priority, spec in enumerate(_TASK_TEMPLATE):
                key = str(spec["key"])
                stage_step = steps.get(str(spec["stage"]))
                task = MissionTask(
                    project_id=project_id,
                    mission_id=mission.id,
                    mission_step_id=stage_step.id if stage_step is not None else None,
                    task_key=key,
                    title=str(spec["title"]),
                    role=str(spec["role"]),
                    agent_type=str(spec["agent"]) if spec.get("agent") else None,
                    status=MissionTaskStatus.DRAFT,
                    priority=priority * 10,
                    idempotency_key=f"{mission.id}/{key}/v1",
                    input_json={"mission_id": str(mission.id), "task_key": key},
                    acceptance_json=["artifact_hash_recorded"],
                    permissions_json=["project:read", f"role:{spec['role']}"],
                    budget_json={},
                    created_by=actor.id,
                )
                self.db.add(task)
                task_by_key[key] = task
            await self.db.flush()
            self.db.add_all(
                MissionTaskDependency(
                    project_id=project_id,
                    mission_id=mission.id,
                    task_id=task_by_key[task_key].id,
                    depends_on_task_id=task_by_key[dependency_key].id,
                )
                for task_key, dependency_key in _DEPENDENCIES
            )
            self.db.add_all(
                ApprovalGate(
                    project_id=project_id,
                    mission_id=mission.id,
                    task_id=task_by_key[task_key].id,
                    gate_kind=gate_kind,
                    status=ApprovalGateStatus.PENDING,
                    request_json={
                        "phase": phase,
                        "complete_task_on_approval": complete_task,
                    },
                    requested_by=actor.id,
                )
                for task_key, gate_kind, phase, complete_task in _GATES
            )
            for task in task_by_key.values():
                self.db.add(
                    TaskEvent(
                        project_id=project_id,
                        mission_id=mission.id,
                        task_id=task.id,
                        seq=0,
                        event_type="task.created",
                        payload_json={"status": task.status},
                        actor_id=actor.id,
                    )
                )
            await self.db.commit()

        await self._sync_existing_approvals(actor, mission)
        await self._tick_state(mission, actor_id=actor.id)
        await self.db.commit()
        return await self._graph_unchecked(mission.id)

    async def _sync_existing_approvals(self, actor: User, mission: ResearchMission) -> None:
        tasks = {
            task.task_key: task
            for task in (
                (
                    await self.db.execute(
                        select(MissionTask).where(MissionTask.mission_id == mission.id)
                    )
                )
                .scalars()
                .all()
            )
        }
        gates = {
            gate.gate_kind: gate
            for gate in (
                (
                    await self.db.execute(
                        select(ApprovalGate).where(ApprovalGate.mission_id == mission.id)
                    )
                )
                .scalars()
                .all()
            )
        }
        scope_step = await self.db.scalar(
            select(MissionStep).where(
                MissionStep.mission_id == mission.id,
                MissionStep.step_kind == MissionStepKind.SCOPE,
            )
        )
        if scope_step is not None and scope_step.status == MissionStepStatus.COMPLETED:
            await self._complete_external_gate(
                actor,
                tasks.get("scope"),
                gates.get("scope"),
                {"mission_step_id": str(scope_step.id)},
                "mission-step/v1",
            )

        idea = await self.db.scalar(
            select(Idea)
            .where(Idea.project_id == mission.project_id, Idea.status == IdeaStatus.ACTIVE)
            .limit(1)
        )
        if idea is not None:
            await self._complete_external_gate(
                actor,
                tasks.get("direction"),
                gates.get("direction"),
                {"idea_id": str(idea.id), "title": idea.title},
                "approved-direction/v1",
            )
            snapshot = await self.db.scalar(
                select(RepositorySnapshot)
                .where(
                    RepositorySnapshot.project_id == mission.project_id,
                    RepositorySnapshot.idea_id == idea.id,
                    RepositorySnapshot.status == "ready",
                )
                .order_by(RepositorySnapshot.imported_at.desc())
                .limit(1)
            )
            if snapshot is not None:
                await self._complete_external_gate(
                    actor,
                    tasks.get("repository"),
                    gates.get("repository_import"),
                    {
                        "snapshot_id": str(snapshot.id),
                        "commit_sha": snapshot.commit_sha,
                        "destination_path": snapshot.destination_path,
                    },
                    "repository-snapshot/v1",
                    content_hash=snapshot.manifest_hash,
                    uri=snapshot.destination_path,
                )

    async def _complete_external_gate(
        self,
        actor: User,
        task: MissionTask | None,
        gate: ApprovalGate | None,
        output: dict,
        schema_name: str,
        *,
        content_hash: str | None = None,
        uri: str | None = None,
    ) -> None:
        if task is None or gate is None or task.status == MissionTaskStatus.COMPLETED:
            return
        now = _now()
        gate.status = ApprovalGateStatus.APPROVED
        gate.decided_by = actor.id
        gate.decided_at = now
        gate.decision_json = {"source": "existing_approved_artifact"}
        task.status = MissionTaskStatus.COMPLETED
        task.output_json = output
        task.finished_at = now
        digest = content_hash or _hash_payload(output)
        existing = await self.db.scalar(
            select(TaskArtifact.id).where(
                TaskArtifact.task_id == task.id,
                TaskArtifact.schema_name == schema_name,
                TaskArtifact.content_hash == digest,
            )
        )
        if existing is None:
            self.db.add(
                TaskArtifact(
                    project_id=task.project_id,
                    mission_id=task.mission_id,
                    task_id=task.id,
                    schema_name=schema_name,
                    schema_version=1,
                    content_hash=digest,
                    uri=uri,
                    metadata_json=output,
                    created_by=actor.id,
                    visibility="team",
                )
            )

    async def tick(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> CoordinatorTickResponse:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        await self.db.execute(
            select(ResearchMission.id).where(ResearchMission.id == mission.id).with_for_update()
        )
        await self._sync_existing_approvals(actor, mission)
        promoted, reclaimed, reconciled = await self._tick_state(mission, actor_id=actor.id)
        await self.db.commit()
        return CoordinatorTickResponse(
            graph=await self._graph_unchecked(mission.id),
            promoted=promoted,
            reclaimed=reclaimed,
            reconciled=reconciled,
        )

    async def _tick_state(
        self, mission: ResearchMission, *, actor_id: uuid.UUID | None
    ) -> tuple[int, int, int]:
        if mission.status in {MissionStatus.PAUSED, MissionStatus.ARCHIVED}:
            return 0, 0, 0
        now = _now()
        reclaimed = 0
        expired = list(
            (
                await self.db.execute(
                    select(TaskLease).where(
                        TaskLease.mission_id == mission.id, TaskLease.expires_at <= now
                    )
                )
            )
            .scalars()
            .all()
        )
        for lease in expired:
            task = await self.db.get(MissionTask, lease.task_id)
            if task is not None and task.status in {
                MissionTaskStatus.LEASED,
                MissionTaskStatus.RUNNING,
            }:
                task.status = (
                    MissionTaskStatus.RETRYABLE_FAILED
                    if task.attempt < task.max_attempts
                    else MissionTaskStatus.TERMINAL_FAILED
                )
                if task.status == MissionTaskStatus.RETRYABLE_FAILED:
                    task.available_at = now + timedelta(seconds=min(task.attempt**2, 60))
                task.last_error_json = {"code": "lease_expired", "owner": lease.owner}
                await self._event(
                    task,
                    "task.lease_expired",
                    {"owner": lease.owner, "status": task.status},
                    actor_id=actor_id,
                )
                reclaimed += 1
            await self.db.delete(lease)

        reconciled = 0
        linked = list(
            (
                await self.db.execute(
                    select(MissionTask).where(
                        MissionTask.mission_id == mission.id,
                        MissionTask.agent_run_id.is_not(None),
                        MissionTask.status == MissionTaskStatus.RUNNING,
                    )
                )
            )
            .scalars()
            .all()
        )
        for task in linked:
            run = await self.db.get(AgentRun, task.agent_run_id)
            if run is None or not run.status.is_terminal:
                continue
            if await self._apply_terminal_run(task, run, actor_id=actor_id):
                reconciled += 1

        tasks = list(
            (await self.db.execute(select(MissionTask).where(MissionTask.mission_id == mission.id)))
            .scalars()
            .all()
        )
        completed = {task.id for task in tasks if task.status == MissionTaskStatus.COMPLETED}
        dependencies = list(
            (
                await self.db.execute(
                    select(MissionTaskDependency).where(
                        MissionTaskDependency.mission_id == mission.id
                    )
                )
            )
            .scalars()
            .all()
        )
        parents: dict[uuid.UUID, set[uuid.UUID]] = {}
        for edge in dependencies:
            parents.setdefault(edge.task_id, set()).add(edge.depends_on_task_id)
        promoted = 0
        for task in tasks:
            if task.status not in {
                MissionTaskStatus.DRAFT,
                MissionTaskStatus.RETRYABLE_FAILED,
            }:
                continue
            if task.available_at is not None and task.available_at > now:
                continue
            if not parents.get(task.id, set()).issubset(completed):
                continue
            before_gate = await self.db.scalar(
                select(ApprovalGate).where(
                    ApprovalGate.task_id == task.id,
                    ApprovalGate.status == ApprovalGateStatus.PENDING,
                    ApprovalGate.request_json["phase"].astext == "before",
                )
            )
            task.status = (
                MissionTaskStatus.WAITING_APPROVAL
                if before_gate is not None
                else MissionTaskStatus.READY
            )
            task.available_at = now
            await self._event(
                task,
                "task.promoted",
                {"status": task.status},
                actor_id=actor_id,
            )
            promoted += 1
        return promoted, reclaimed, reconciled

    async def reconcile_run(self, run: AgentRun) -> bool:
        """Atomically fold a terminal AgentRun into its durable task.

        The runtime calls this before its final commit. Looking up by the
        context task id also closes the small window where the broker starts a
        run before the HTTP dispatcher has persisted ``task.agent_run_id``.
        """

        if not run.status.is_terminal:
            return False
        raw_task_id = (run.input_json.get("context") or {}).get("mission_task_id")
        try:
            task_id = uuid.UUID(str(raw_task_id))
        except (TypeError, ValueError):
            return False
        task = await self.db.scalar(
            select(MissionTask)
            .where(MissionTask.id == task_id, MissionTask.project_id == run.project_id)
            .with_for_update()
        )
        if task is None:
            return False
        task.agent_run_id = run.id
        return await self._apply_terminal_run(task, run, actor_id=run.user_id)

    async def _apply_terminal_run(
        self, task: MissionTask, run: AgentRun, *, actor_id: uuid.UUID | None
    ) -> bool:
        if task.status not in {MissionTaskStatus.RUNNING, MissionTaskStatus.LEASED}:
            return False
        now = _now()
        if run.status == AgentRunStatus.COMPLETED:
            output = run.output_json or {}
            await self._record_artifact(
                task,
                created_by=run.user_id,
                producer_run_id=run.id,
                submission=ArtifactSubmission(
                    schema_name=f"agent-run/{run.agent_type.value}",
                    content_hash=_hash_payload(output),
                    metadata=output,
                ),
            )
            task.output_json = output
            task.status = await self._post_output_status(task)
            if task.status == MissionTaskStatus.COMPLETED:
                task.finished_at = now
                await self._promote_dependents(task, actor_id=actor_id)
            await self._event(
                task,
                "task.agent_completed",
                {"agent_run_id": str(run.id), "status": task.status},
                actor_id=actor_id,
            )
        else:
            task.last_error_json = run.error_json or {"code": run.status.value}
            task.status = (
                MissionTaskStatus.RETRYABLE_FAILED
                if task.attempt < task.max_attempts
                else MissionTaskStatus.TERMINAL_FAILED
            )
            if task.status == MissionTaskStatus.RETRYABLE_FAILED:
                task.available_at = now + timedelta(seconds=min(task.attempt**2, 60))
            task.agent_run_id = None
            await self._event(
                task,
                "task.agent_failed",
                {"agent_run_id": str(run.id), "status": task.status},
                actor_id=actor_id,
            )
        return True

    async def _post_output_status(self, task: MissionTask) -> MissionTaskStatus:
        after_gate = await self.db.scalar(
            select(ApprovalGate.id).where(
                ApprovalGate.task_id == task.id,
                ApprovalGate.status == ApprovalGateStatus.PENDING,
                ApprovalGate.request_json["phase"].astext == "after",
            )
        )
        return (
            MissionTaskStatus.WAITING_APPROVAL
            if after_gate is not None
            else MissionTaskStatus.COMPLETED
        )

    async def _promote_dependents(
        self, task: MissionTask, *, actor_id: uuid.UUID | None
    ) -> int:
        """Unlock direct children after a durable completion.

        Coordinator ticks remain the recovery path for simultaneous parent
        completions; the normal chain advances without a user action.
        """

        child_ids = list(
            (
                await self.db.execute(
                    select(MissionTaskDependency.task_id).where(
                        MissionTaskDependency.depends_on_task_id == task.id
                    )
                )
            )
            .scalars()
            .all()
        )
        promoted = 0
        now = _now()
        for child_id in child_ids:
            child = await self.db.get(MissionTask, child_id)
            if child is None or child.status not in {
                MissionTaskStatus.DRAFT,
                MissionTaskStatus.RETRYABLE_FAILED,
            }:
                continue
            incomplete = await self.db.scalar(
                select(func.count())
                .select_from(MissionTaskDependency)
                .join(
                    MissionTask,
                    MissionTask.id == MissionTaskDependency.depends_on_task_id,
                )
                .where(
                    MissionTaskDependency.task_id == child.id,
                    MissionTask.status != MissionTaskStatus.COMPLETED,
                )
            )
            if incomplete:
                continue
            before_gate = await self.db.scalar(
                select(ApprovalGate.id).where(
                    ApprovalGate.task_id == child.id,
                    ApprovalGate.status == ApprovalGateStatus.PENDING,
                    ApprovalGate.request_json["phase"].astext == "before",
                )
            )
            child.status = (
                MissionTaskStatus.WAITING_APPROVAL
                if before_gate is not None
                else MissionTaskStatus.READY
            )
            child.available_at = now
            await self._event(
                child,
                "task.promoted",
                {"status": child.status, "completed_dependency": str(task.id)},
                actor_id=actor_id,
            )
            promoted += 1
        return promoted

    async def dispatch(
        self,
        actor: User,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        message: str,
        context: dict,
    ) -> DispatchTaskResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        task = await self.db.scalar(
            select(MissionTask)
            .where(MissionTask.id == task_id, MissionTask.project_id == project_id)
            .with_for_update()
        )
        if task is None:
            raise NotFoundError("Mission task not found.")
        if task.status != MissionTaskStatus.READY:
            raise ConflictError("Only a ready task can be dispatched.")
        if task.agent_type is None:
            raise ValidationError(
                "This task is completed by an external artifact or approval gate."
            )
        if task.attempt >= task.max_attempts:
            raise ConflictError("The task exhausted its retry budget.")
        active_config = await self.db.scalar(
            select(LLMProviderConfig.id)
            .where(
                LLMProviderConfig.project_id == project_id,
                LLMProviderConfig.is_active.is_(True),
            )
            .limit(1)
        )
        if active_config is None:
            raise ConflictError(
                "Configure and test an active model before dispatching Agent tasks.",
                code="real_llm_required",
            )
        try:
            agent_type = AgentType(task.agent_type)
        except ValueError as exc:
            raise ValidationError("Task agent type is not supported by the runtime.") from exc
        run_context = {**task.input_json, **context, "mission_task_id": str(task.id)}
        if agent_type == AgentType.CRITIC and not run_context.get("idea_id"):
            active_idea = await self.db.scalar(
                select(Idea.id)
                .where(Idea.project_id == project_id, Idea.status == IdeaStatus.ACTIVE)
                .limit(1)
            )
            if active_idea is None:
                raise ValidationError("Critic task requires an idea_id or active direction.")
            run_context["idea_id"] = str(active_idea)
        task.status = MissionTaskStatus.RUNNING
        task.attempt += 1
        task.started_at = task.started_at or _now()
        await self._event(
            task,
            "task.dispatching",
            {"agent_type": agent_type.value, "attempt": task.attempt},
            actor_id=actor.id,
        )
        run = await AgentRunService(self.db).create_run(
            actor,
            project_id,
            agent_type=agent_type,
            message=message,
            context=run_context,
        )
        task.agent_run_id = run.id
        await self.db.commit()
        return DispatchTaskResponse(
            task_id=task.id,
            agent_run_id=run.id,
            status=task.status,
            stream=f"/ws?project_id={project_id}",
        )

    async def lease_next(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        owner: str,
        role: str | None,
        lease_seconds: int,
    ) -> LeaseTaskResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        query = (
            select(MissionTask)
            .join(ResearchMission, ResearchMission.id == MissionTask.mission_id)
            .where(
                MissionTask.project_id == project_id,
                MissionTask.status == MissionTaskStatus.READY,
                MissionTask.attempt < MissionTask.max_attempts,
                ResearchMission.status.not_in([MissionStatus.PAUSED, MissionStatus.ARCHIVED]),
            )
            .order_by(MissionTask.priority.asc(), MissionTask.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if role:
            query = query.where(MissionTask.role == role)
        task = await self.db.scalar(query)
        if task is None:
            raise NotFoundError("No runnable mission task is available.")
        now = _now()
        task.status = MissionTaskStatus.LEASED
        task.attempt += 1
        lease = TaskLease(
            project_id=project_id,
            mission_id=task.mission_id,
            task_id=task.id,
            owner=owner,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=lease_seconds),
        )
        self.db.add(lease)
        await self._event(
            task,
            "task.leased",
            {"owner": owner, "attempt": task.attempt, "expires_at": lease.expires_at},
            actor_id=actor.id,
        )
        await self.db.commit()
        await self.db.refresh(lease)
        return LeaseTaskResponse(
            task=MissionTaskResponse.model_validate(task),
            lease_token=lease.token,
            expires_at=lease.expires_at,
        )

    async def heartbeat(
        self,
        actor: User,
        project_id: uuid.UUID,
        token: uuid.UUID,
        *,
        lease_seconds: int,
        running: bool,
    ) -> TaskLease:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        lease = await self.db.scalar(
            select(TaskLease)
            .where(TaskLease.token == token, TaskLease.project_id == project_id)
            .with_for_update()
        )
        if lease is None:
            raise NotFoundError("Task lease not found.")
        now = _now()
        if lease.expires_at <= now:
            raise ConflictError("Task lease expired.")
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(seconds=lease_seconds)
        if running:
            task = await self.db.get(MissionTask, lease.task_id)
            if task is not None and task.status == MissionTaskStatus.LEASED:
                task.status = MissionTaskStatus.RUNNING
                task.started_at = task.started_at or now
        await self.db.commit()
        await self.db.refresh(lease)
        return lease

    async def submit_lease(
        self,
        actor: User,
        project_id: uuid.UUID,
        token: uuid.UUID,
        *,
        output: dict,
        artifacts: list[ArtifactSubmission],
    ) -> MissionTask:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        lease = await self.db.scalar(
            select(TaskLease)
            .where(TaskLease.token == token, TaskLease.project_id == project_id)
            .with_for_update()
        )
        if lease is None:
            raise NotFoundError("Task lease not found.")
        now = _now()
        if lease.expires_at <= now:
            raise ConflictError("Task lease expired.")
        task = await self.db.scalar(
            select(MissionTask).where(MissionTask.id == lease.task_id).with_for_update()
        )
        if task is None or task.status not in {
            MissionTaskStatus.LEASED,
            MissionTaskStatus.RUNNING,
        }:
            raise ConflictError("Task is not owned by an active worker lease.")
        if "artifact_hash_recorded" in task.acceptance_json and not artifacts:
            raise ValidationError("This task requires at least one hashed artifact.")
        for submission in artifacts:
            await self._record_artifact(
                task,
                created_by=actor.id,
                producer_run_id=task.agent_run_id,
                submission=submission,
            )
        task.output_json = output
        task.status = await self._post_output_status(task)
        if task.status == MissionTaskStatus.COMPLETED:
            task.finished_at = now
            await self._promote_dependents(task, actor_id=actor.id)
        await self._event(
            task,
            "task.submitted",
            {"artifact_count": len(artifacts), "status": task.status},
            actor_id=actor.id,
        )
        await self.db.delete(lease)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def _record_artifact(
        self,
        task: MissionTask,
        *,
        created_by: uuid.UUID,
        producer_run_id: uuid.UUID | None,
        submission: ArtifactSubmission,
    ) -> TaskArtifact:
        existing = await self.db.scalar(
            select(TaskArtifact).where(
                TaskArtifact.task_id == task.id,
                TaskArtifact.schema_name == submission.schema_name,
                TaskArtifact.content_hash == submission.content_hash,
            )
        )
        if existing is not None:
            return existing
        artifact = TaskArtifact(
            project_id=task.project_id,
            mission_id=task.mission_id,
            task_id=task.id,
            schema_name=submission.schema_name,
            schema_version=submission.schema_version,
            content_hash=submission.content_hash,
            uri=submission.uri,
            metadata_json=submission.metadata,
            input_artifact_versions_json=submission.input_artifact_versions,
            producer_run_id=producer_run_id,
            created_by=created_by,
            visibility=submission.visibility,
        )
        self.db.add(artifact)
        return artifact

    async def decide_gate(
        self,
        actor: User,
        project_id: uuid.UUID,
        gate_id: uuid.UUID,
        *,
        approve: bool,
        note: str,
    ) -> MissionTask:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        gate = await self.db.scalar(
            select(ApprovalGate)
            .where(ApprovalGate.id == gate_id, ApprovalGate.project_id == project_id)
            .with_for_update()
        )
        if gate is None:
            raise NotFoundError("Approval gate not found.")
        if gate.status != ApprovalGateStatus.PENDING:
            raise ConflictError("Approval gate has already been decided.")
        task = await self.db.scalar(
            select(MissionTask).where(MissionTask.id == gate.task_id).with_for_update()
        )
        if task is None:
            raise NotFoundError("Mission task not found.")
        now = _now()
        if approve and gate.gate_kind == "scope":
            mission = await self.db.get(ResearchMission, task.mission_id)
            if mission is None:
                raise NotFoundError("Research mission not found.")
            await self._complete_external_gate(
                actor,
                task,
                gate,
                {"scope": mission.scope_json, "objective": mission.objective},
                "mission-scope/v1",
            )
            await self._event(
                task,
                "gate.approved",
                {"gate_kind": gate.gate_kind, "source": "mission_scope"},
                actor_id=actor.id,
                message=note,
            )
            await self._promote_dependents(task, actor_id=actor.id)
            await self.db.commit()
            await self.db.refresh(task)
            return task
        if approve and gate.gate_kind == "direction":
            idea = await self.db.scalar(
                select(Idea)
                .where(Idea.project_id == project_id, Idea.status == IdeaStatus.ACTIVE)
                .limit(1)
            )
            if idea is None:
                raise ConflictError("Approve a Critic-reviewed research direction first.")
            await self._complete_external_gate(
                actor,
                task,
                gate,
                {"idea_id": str(idea.id), "title": idea.title},
                "approved-direction/v1",
            )
            await self._event(
                task,
                "gate.approved",
                {"gate_kind": gate.gate_kind, "source": "active_direction"},
                actor_id=actor.id,
                message=note,
            )
            await self._promote_dependents(task, actor_id=actor.id)
            await self.db.commit()
            await self.db.refresh(task)
            return task
        if approve and gate.gate_kind == "repository_import":
            active_idea_id = await self.db.scalar(
                select(Idea.id)
                .where(Idea.project_id == project_id, Idea.status == IdeaStatus.ACTIVE)
                .limit(1)
            )
            snapshot = await self.db.scalar(
                select(RepositorySnapshot)
                .where(
                    RepositorySnapshot.project_id == project_id,
                    RepositorySnapshot.idea_id == active_idea_id,
                    RepositorySnapshot.status == "ready",
                )
                .order_by(RepositorySnapshot.imported_at.desc())
                .limit(1)
            )
            if snapshot is None:
                raise ConflictError("Import an approved repository snapshot first.")
            await self._complete_external_gate(
                actor,
                task,
                gate,
                {
                    "snapshot_id": str(snapshot.id),
                    "commit_sha": snapshot.commit_sha,
                    "destination_path": snapshot.destination_path,
                },
                "repository-snapshot/v1",
                content_hash=snapshot.manifest_hash,
                uri=snapshot.destination_path,
            )
            await self._event(
                task,
                "gate.approved",
                {"gate_kind": gate.gate_kind, "source": "repository_snapshot"},
                actor_id=actor.id,
                message=note,
            )
            await self._promote_dependents(task, actor_id=actor.id)
            await self.db.commit()
            await self.db.refresh(task)
            return task
        if approve and gate.gate_kind == "patch_apply":
            patch_id = task.output_json.get("patch_id")
            try:
                parsed_patch_id = uuid.UUID(str(patch_id))
            except (TypeError, ValueError) as exc:
                raise ConflictError("The Coding Agent has not produced a patch proposal.") from exc
            patch = await self.db.get(PatchProposal, parsed_patch_id)
            if (
                patch is None
                or patch.project_id != project_id
                or patch.status != PatchStatus.APPLIED
            ):
                raise ConflictError("Apply the reviewed patch in the AI IDE before approval.")
        gate.status = ApprovalGateStatus.APPROVED if approve else ApprovalGateStatus.REJECTED
        gate.decided_by = actor.id
        gate.decided_at = now
        gate.decision_json = {"note": note}
        if approve:
            complete = bool(gate.request_json.get("complete_task_on_approval"))
            phase = gate.request_json.get("phase")
            if complete or phase == "after":
                task.status = MissionTaskStatus.COMPLETED
                task.finished_at = now
            else:
                task.status = MissionTaskStatus.READY
                task.available_at = now
        else:
            task.status = MissionTaskStatus.TERMINAL_FAILED
            task.finished_at = now
            task.last_error_json = {"code": "gate_rejected", "gate_kind": gate.gate_kind}
        await self._event(
            task,
            "gate.approved" if approve else "gate.rejected",
            {"gate_kind": gate.gate_kind, "status": task.status},
            actor_id=actor.id,
            message=note,
        )
        if task.status == MissionTaskStatus.COMPLETED:
            await self._promote_dependents(task, actor_id=actor.id)
        await self.db.commit()
        await self.db.refresh(task)
        return task
