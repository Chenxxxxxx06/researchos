# ruff: noqa: E501
"""Coordinator state machine for durable mission task DAGs."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.service import AgentRunService
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.paths import get_local_workspace_selection
from researchos.common.roles import ProjectRole
from researchos.experiment_plans.models import ExperimentPlan
from researchos.experiments.enums import ExperimentRunStatus
from researchos.experiments.models import Experiment, ExperimentRun
from researchos.git.models import RepositorySnapshot
from researchos.identity.models import User
from researchos.knowledge.models import MissionPaper, ReadingCard
from researchos.llm_config.models import LLMProviderConfig
from researchos.missions.enums import MissionStatus, MissionStepKind, MissionStepStatus
from researchos.missions.models import MissionStep, ResearchMission
from researchos.patches.enums import PatchStatus
from researchos.patches.models import PatchProposal
from researchos.projects.service import ProjectService
from researchos.research.enums import IdeaStatus
from researchos.research.models import Idea
from researchos.reviews.models import ReviewDocument

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
    ActiveAgentStatus,
    ArtifactSubmission,
    AutopilotStartRequest,
    AutopilotStepResponse,
    CoordinatorTickResponse,
    DispatchTaskResponse,
    LeaseTaskResponse,
    MissionProgressResponse,
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
        "title": "Extract paper insights and tuple RAG",
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
        "key": "idea_rank",
        "title": "Rank the Top 10 research directions",
        "role": "idea_explorer",
        "agent": "idea_explorer",
        "stage": "review",
    },
    {
        "key": "benchmark",
        "title": "Select credible benchmarks and ablations",
        "role": "benchmark_planner",
        "agent": "benchmark",
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
        "title": "Choose one direction for the next pilot",
        "role": "leader",
        "agent": "leader",
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
        "title": "Implement one direction in the workspace",
        "role": "coding",
        "agent": "coding",
        "stage": "experiment_plan",
    },
    {
        "key": "code_check",
        "title": "Check code, tests, and runnable receipt",
        "role": "viewer",
        "agent": "viewer",
        "stage": "experiment_plan",
    },
    {
        "key": "pilot",
        "title": "Run a bounded small-batch pilot",
        "role": "experiment_runner",
        "agent": "experiment",
        "stage": "experiment_plan",
    },
    {
        "key": "pilot_review",
        "title": "Review pilot evidence and failure modes",
        "role": "viewer",
        "agent": "viewer",
        "stage": "experiment_plan",
    },
    {
        "key": "leader",
        "title": "Decide revise, next direction, or scale",
        "role": "leader",
        "agent": "leader",
        "stage": "experiment_plan",
    },
    {
        "key": "experiment_plan",
        "title": "Build full benchmark and ablation DAG",
        "role": "experiment_planner",
        "agent": "experiment_planner",
        "stage": "experiment_plan",
    },
    {
        "key": "experiment_run",
        "title": "Run approved full experiment matrix",
        "role": "experiment_runner",
        "agent": "experiment",
        "stage": "experiment_plan",
    },
    {
        "key": "progress",
        "title": "Monitor runs, blockers, progress, and ETA",
        "role": "progress_controller",
        "agent": "progress",
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
        "title": "Analyze results, ablations, and negative evidence",
        "role": "analyst",
        "agent": "experiment",
        "stage": "experiment_plan",
    },
    {
        "key": "writer_outline",
        "title": "Draft venue-aware paper skeleton in parallel",
        "role": "writer",
        "agent": "writer",
        "stage": "review",
    },
    {
        "key": "writer_results",
        "title": "Write evidence-bound result sections",
        "role": "writer",
        "agent": "writer",
        "stage": "review",
    },
    {
        "key": "drawer",
        "title": "Generate figures, tables, and method flow",
        "role": "drawer",
        "agent": "drawer",
        "stage": "review",
    },
    {
        "key": "citation",
        "title": "Insert and audit citations",
        "role": "citation_organizer",
        "agent": "citation_organizer",
        "stage": "review",
    },
    {
        "key": "review",
        "title": "Viewer review for claims and venue fit",
        "role": "viewer",
        "agent": "viewer",
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
    ("idea_rank", "synthesize"),
    ("benchmark", "read"),
    ("critic", "idea_rank"),
    ("direction", "critic"),
    ("direction", "benchmark"),
    ("repository", "direction"),
    ("baseline", "repository"),
    ("coding", "repository"),
    ("code_check", "coding"),
    ("pilot", "baseline"),
    ("pilot", "code_check"),
    ("pilot_review", "pilot"),
    ("leader", "pilot_review"),
    ("experiment_plan", "leader"),
    ("experiment_run", "experiment_plan"),
    ("progress", "experiment_run"),
    ("reproduce", "experiment_run"),
    ("reproduce", "progress"),
    ("analyze", "reproduce"),
    ("writer_outline", "direction"),
    ("writer_results", "writer_outline"),
    ("writer_results", "analyze"),
    ("drawer", "writer_results"),
    ("citation", "writer_results"),
    ("review", "drawer"),
    ("review", "citation"),
    ("release", "review"),
)

_AUTOPILOT_MESSAGES: dict[str, str] = {
    "discover": "Search the project corpus and external literature for the mission scope; report only retrievable sources.",
    "read": "Extract summary, experiment results, GitHub/code links, reusable ideas, benchmarks, ablations, and evidence-linked tuples from this paper.",
    "synthesize": "Synthesize the mission evidence, conflicts, limitations, and reusable findings with source citations.",
    "idea_rank": "Rank at most ten falsifiable directions and define a cheap pilot for each.",
    "benchmark": "Select the most credible benchmarks and design pilot/full baseline and ablation matrices.",
    "critic": "Critique the highest-ranked unreviewed direction for novelty, feasibility, baselines, and risk.",
    "direction": "Choose exactly one direction for the next bounded pilot.",
    "baseline": "Build a reproducible baseline and experiment plan from the reviewed evidence.",
    "coding": "Implement only the selected direction, add tests, and keep the change small enough for a pilot.",
    "code_check": "Audit the implementation patch, tests, commit, and runnable receipts before any pilot.",
    "pilot": "Analyze the recorded small-batch pilot run and report observed metrics only.",
    "pilot_review": "Review the pilot for integrity, leakage, instability, reproducibility, and information gain.",
    "leader": "Decide whether to revise code, try the next direction, scale experiments, write, or stop.",
    "experiment_plan": "Finalize the benchmark, baseline, seed, metric, ablation, decision, and stop-rule matrix.",
    "experiment_run": "Analyze the approved full experiment run using only persisted metrics.",
    "progress": "Report real-time task progress, active agents, blockers, and evidence-based next actions.",
    "reproduce": "Audit the reproduced run and compare it with the primary result.",
    "analyze": "Analyze full results, ablations, negative findings, and supported claims.",
    "writer_outline": "Draft a venue-aware paper skeleton while experiments continue.",
    "writer_results": "Draft the results and discussion using only verified metrics and citation keys.",
    "drawer": "Generate the method flow, result figures, LaTeX tables, and evidence-bound captions.",
    "citation": "Audit all mission citations and produce verified BibTeX.",
    "review": "Perform an independent Viewer review against the target venue and evidence receipts.",
    "release": "Prepare the final repository release patch without publishing it.",
}

_GATES: tuple[tuple[str, str, str, bool], ...] = (
    ("scope", "scope", "before", True),
    ("repository", "repository_import", "before", True),
    ("coding", "patch_apply", "after", True),
    ("experiment_run", "compute", "before", False),
    ("release", "release", "after", True),
)


def _validate_local_autopilot_argv(argv: list[str]) -> None:
    if not argv:
        raise ValidationError("A local experiment command is required.")
    executable = argv[0].lower()
    if executable == "pytest":
        if any(value in {"--pdb", "--trace"} for value in argv[1:]):
            raise ValidationError("Interactive pytest flags are not allowed in autopilot.")
        return
    if (
        executable in {"python", "python3"}
        and len(argv) >= 3
        and argv[1] == "-m"
        and argv[2] in {"compileall", "pytest"}
    ):
        return
    raise ValidationError(
        "Trusted local autopilot accepts only pytest or python -m compileall/pytest. "
        "Use an isolated SSH/container runner for arbitrary training commands."
    )


def _mission_progress(
    tasks: list[MissionTask], gates: list[ApprovalGate]
) -> MissionProgressResponse:
    tasks = [task for task in tasks if not (task.output_json or {}).get("deprecated_by_template")]
    total = len(tasks)
    completed = sum(task.status == MissionTaskStatus.COMPLETED for task in tasks)
    running = sum(
        task.status in {MissionTaskStatus.LEASED, MissionTaskStatus.RUNNING} for task in tasks
    )
    failed = sum(
        task.status in {MissionTaskStatus.RETRYABLE_FAILED, MissionTaskStatus.TERMINAL_FAILED}
        for task in tasks
    )
    blocked = sum(
        task.status in {MissionTaskStatus.DRAFT, MissionTaskStatus.WAITING_APPROVAL}
        for task in tasks
    )
    active = [
        ActiveAgentStatus(
            task_id=task.id,
            task_key=task.task_key,
            title=task.title,
            role=task.role,
            agent_type=task.agent_type,
            status=task.status,
            agent_run_id=task.agent_run_id,
            attempt=task.attempt,
            started_at=task.started_at,
            progress_percent=(25.0 if task.status == MissionTaskStatus.LEASED else 50.0),
            current_action=str(task.output_json.get("current_action") or task.title),
        )
        for task in tasks
        if task.status in {MissionTaskStatus.LEASED, MissionTaskStatus.RUNNING}
    ]
    incomplete = next(
        (
            task
            for task in sorted(tasks, key=lambda item: item.priority)
            if task.status != MissionTaskStatus.COMPLETED
        ),
        None,
    )
    stage_by_key = {str(item["key"]): str(item["stage"]) for item in _TASK_TEMPLATE}
    durations = [
        (task.finished_at - task.started_at).total_seconds()
        for task in tasks
        if task.status == MissionTaskStatus.COMPLETED
        and task.started_at is not None
        and task.finished_at is not None
        and task.finished_at >= task.started_at
    ]
    remaining = max(0, total - completed)
    eta = int((sum(durations) / len(durations)) * remaining) if durations else None
    pending_gate_tasks = {
        gate.task_id: gate.gate_kind for gate in gates if gate.status == ApprovalGateStatus.PENDING
    }
    blockers = [
        f"{task.task_key}: approval required ({pending_gate_tasks[task.id]})"
        for task in tasks
        if task.id in pending_gate_tasks and task.status == MissionTaskStatus.WAITING_APPROVAL
    ]
    blockers.extend(
        f"{task.task_key}: {str((task.last_error_json or {}).get('code') or 'failed')}"
        for task in tasks
        if task.last_error_json
    )
    return MissionProgressResponse(
        total_tasks=total,
        completed_tasks=completed,
        running_tasks=running,
        blocked_tasks=blocked,
        failed_tasks=failed,
        progress_percent=round(100 * completed / total, 2) if total else 0.0,
        active_agents=active,
        current_phase=stage_by_key.get(incomplete.task_key, "completed")
        if incomplete
        else "completed",
        next_ready_tasks=[
            task.task_key for task in tasks if task.status == MissionTaskStatus.READY
        ],
        blocker_messages=blockers[:30],
        eta_seconds=eta,
        eta_basis=(
            "mean completed task duration" if durations else "insufficient completed-task history"
        ),
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
                payload_json=jsonable_encoder(payload),
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
            progress=_mission_progress(tasks, gates),
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
        if existing:
            await self._upgrade_graph_template(actor, mission)
        else:
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

    async def _upgrade_graph_template(self, actor: User, mission: ResearchMission) -> None:
        """Idempotently add new research-program roles to an older mission DAG."""

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
        task_by_key = {
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
        desired_keys = {str(item["key"]) for item in _TASK_TEMPLATE}
        for priority, spec in enumerate(_TASK_TEMPLATE):
            key = str(spec["key"])
            task = task_by_key.get(key)
            if task is None:
                stage_step = steps.get(str(spec["stage"]))
                task = MissionTask(
                    project_id=mission.project_id,
                    mission_id=mission.id,
                    mission_step_id=stage_step.id if stage_step is not None else None,
                    task_key=key,
                    title=str(spec["title"]),
                    role=str(spec["role"]),
                    agent_type=str(spec["agent"]) if spec.get("agent") else None,
                    status=MissionTaskStatus.DRAFT,
                    priority=priority * 10,
                    idempotency_key=f"{mission.id}/{key}/v2",
                    input_json={"mission_id": str(mission.id), "task_key": key},
                    acceptance_json=["artifact_hash_recorded"],
                    permissions_json=["project:read", f"role:{spec['role']}"],
                    budget_json={"pilot_first": True},
                    created_by=actor.id,
                )
                self.db.add(task)
                await self.db.flush()
                task_by_key[key] = task
                await self._event(
                    task,
                    "task.created",
                    {"status": task.status, "template_version": 2},
                    actor_id=actor.id,
                )
            else:
                task.title = str(spec["title"])
                task.role = str(spec["role"])
                task.agent_type = str(spec["agent"]) if spec.get("agent") else None
                task.priority = priority * 10
                task.input_json = {
                    **task.input_json,
                    "mission_id": str(mission.id),
                    "task_key": key,
                }

        for key, task in task_by_key.items():
            if key in desired_keys:
                continue
            task.output_json = {
                **task.output_json,
                "deprecated_by_template": 2,
                "task_key": key,
                "historical_status": task.status,
            }
            if task.status not in {
                MissionTaskStatus.COMPLETED,
                MissionTaskStatus.CANCELLED,
                MissionTaskStatus.TERMINAL_FAILED,
            }:
                task.status = MissionTaskStatus.COMPLETED
                task.finished_at = _now()
            await self._event(
                task,
                "task.deprecated",
                task.output_json,
                actor_id=actor.id,
            )

        edge_rows = list(
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
        existing_edges = {(edge.task_id, edge.depends_on_task_id) for edge in edge_rows}
        desired_edges = {
            (task_by_key[task_key].id, task_by_key[dependency_key].id)
            for task_key, dependency_key in _DEPENDENCIES
        }
        for edge in edge_rows:
            if (edge.task_id, edge.depends_on_task_id) not in desired_edges:
                await self.db.delete(edge)
        for task_key, dependency_key in _DEPENDENCIES:
            edge_key = (task_by_key[task_key].id, task_by_key[dependency_key].id)
            if edge_key not in existing_edges:
                self.db.add(
                    MissionTaskDependency(
                        project_id=mission.project_id,
                        mission_id=mission.id,
                        task_id=edge_key[0],
                        depends_on_task_id=edge_key[1],
                    )
                )

        desired_gates = {(task_key, gate_kind) for task_key, gate_kind, _, _ in _GATES}
        existing_gates = list(
            (
                await self.db.execute(
                    select(ApprovalGate).where(ApprovalGate.mission_id == mission.id)
                )
            )
            .scalars()
            .all()
        )
        by_gate = {
            (
                next(key for key, task in task_by_key.items() if task.id == gate.task_id),
                gate.gate_kind,
            ): gate
            for gate in existing_gates
        }
        for gate_key, gate in by_gate.items():
            if gate_key not in desired_gates and gate.status == ApprovalGateStatus.PENDING:
                gated_task = await self.db.get(MissionTask, gate.task_id)
                await self.db.delete(gate)
                if (
                    gated_task is not None
                    and gated_task.status == MissionTaskStatus.WAITING_APPROVAL
                ):
                    gated_task.status = MissionTaskStatus.DRAFT
                    gated_task.available_at = _now()
        for task_key, gate_kind, phase, complete_task in _GATES:
            if (task_key, gate_kind) not in by_gate:
                self.db.add(
                    ApprovalGate(
                        project_id=mission.project_id,
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
                )
        await self.db.flush()

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
            .where(
                Idea.project_id == mission.project_id,
                Idea.status == IdeaStatus.ACTIVE,
                Idea.metadata_json["mission_id"].astext == str(mission.id),
            )
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

    async def autopilot_step(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        policy: AutopilotStartRequest,
    ) -> AutopilotStepResponse:
        """Dispatch one safe ready task and persist the policy for continuation.

        Each completed AgentRun schedules the next step. The chain stops at a
        credential, repository, compute, integrity, or release gate rather than
        silently broadening permissions.
        """

        await self.bootstrap(actor, project_id, mission_id)
        mission = await self._mission(actor, project_id, mission_id, write=True)
        await self.db.execute(
            select(ResearchMission.id).where(ResearchMission.id == mission.id).with_for_update()
        )
        await self._tick_state(mission, actor_id=actor.id)
        tasks = list(
            (
                await self.db.execute(
                    select(MissionTask)
                    .where(MissionTask.mission_id == mission_id)
                    .order_by(MissionTask.priority.asc())
                )
            )
            .scalars()
            .all()
        )
        policy_json = policy.model_dump(mode="json")
        for task in tasks:
            task.input_json = {**task.input_json, "autopilot_policy": policy_json}
        if tasks and all(
            task.status
            in {
                MissionTaskStatus.COMPLETED,
                MissionTaskStatus.CANCELLED,
            }
            for task in tasks
        ):
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="completed",
                next_action="Research program completed; release still follows its recorded gate.",
            )
        if any(
            task.status in {MissionTaskStatus.LEASED, MissionTaskStatus.RUNNING} for task in tasks
        ):
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="running",
                next_action="Wait for the active agent or runner receipt.",
            )

        active_config = await self.db.scalar(
            select(LLMProviderConfig.id).where(
                LLMProviderConfig.project_id == project_id,
                LLMProviderConfig.is_active.is_(True),
            )
        )
        if active_config is None:
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="blocked",
                blockers=["model_config_required"],
                next_action="Configure and test an active model; credentials are never inferred.",
            )

        ready = [task for task in tasks if task.status == MissionTaskStatus.READY]
        if not ready:
            graph = await self._graph_unchecked(mission_id)
            await self.db.commit()
            return AutopilotStepResponse(
                graph=graph,
                state="blocked",
                blockers=graph.progress.blocker_messages or ["no_runnable_task"],
                next_action="Resolve the displayed approval, artifact, credential, or compute gate.",
            )

        task = ready[0]
        if task.agent_type is None:
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="blocked",
                blockers=[f"{task.task_key}: external artifact or approval required"],
                next_action="Provide the requested repository, API, dataset, or compute approval.",
            )
        context, blocker = await self._autopilot_context(task, policy, actor)
        if blocker == "__advanced__":
            await self.db.commit()
            return await self.autopilot_step(actor, project_id, mission_id, policy)
        if blocker == "__runner_started__":
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="running",
                dispatched_task_id=task.id,
                next_action=f"Bounded {task.task_key} command is running in the isolated workspace.",
            )
        if blocker:
            await self.db.commit()
            return AutopilotStepResponse(
                graph=await self._graph_unchecked(mission_id),
                state="blocked",
                blockers=[f"{task.task_key}: {blocker}"],
                next_action=blocker,
            )
        await self.db.commit()
        dispatched = await self.dispatch(
            actor,
            project_id,
            task.id,
            message=_AUTOPILOT_MESSAGES.get(task.task_key, task.title),
            context={
                **context,
                "autopilot": True,
                "autopilot_policy": policy_json,
            },
        )
        return AutopilotStepResponse(
            graph=await self._graph_unchecked(mission_id),
            state="dispatched",
            dispatched_task_id=task.id,
            agent_run_id=dispatched.agent_run_id,
            next_action=f"{task.role} is executing {task.task_key}.",
        )

    async def _autopilot_context(
        self, task: MissionTask, policy: AutopilotStartRequest, actor: User
    ) -> tuple[dict, str | None]:
        context: dict = {"mission_id": str(task.mission_id)}
        if task.task_key == "read":
            paper_ids = list(
                (
                    await self.db.execute(
                        select(MissionPaper.paper_id)
                        .where(MissionPaper.mission_id == task.mission_id)
                        .order_by(MissionPaper.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            card_ids = set(
                (
                    await self.db.execute(
                        select(ReadingCard.paper_id).where(
                            ReadingCard.mission_id == task.mission_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            remaining = [paper_id for paper_id in paper_ids if paper_id not in card_ids]
            if not paper_ids:
                return context, "Include and ingest papers before automatic reading."
            if not remaining:
                task.status = MissionTaskStatus.COMPLETED
                task.output_json = {
                    "paper_count": len(paper_ids),
                    "reading_card_count": len(card_ids),
                    "status": "corpus_extracted",
                }
                task.finished_at = _now()
                await self._record_artifact(
                    task,
                    created_by=task.created_by,
                    producer_run_id=task.agent_run_id,
                    submission=ArtifactSubmission(
                        schema_name="paper-insight-corpus/v1",
                        content_hash=_hash_payload(task.output_json),
                        metadata=task.output_json,
                    ),
                )
                await self._event(
                    task,
                    "paper_corpus.extracted",
                    task.output_json,
                    actor_id=task.created_by,
                )
                await self._promote_dependents(task, actor_id=task.created_by)
                return context, "__advanced__"
            context.update(
                {
                    "paper_id": str(remaining[0]),
                    "section_kinds": [
                        "abstract",
                        "introduction",
                        "method",
                        "experiments",
                        "results",
                        "conclusion",
                    ],
                }
            )
        elif task.task_key == "idea_rank":
            context["max_directions"] = policy.max_directions
        elif task.task_key == "critic":
            idea = await self.db.scalar(
                select(Idea)
                .where(
                    Idea.project_id == task.project_id,
                    Idea.metadata_json["mission_id"].astext == str(task.mission_id),
                    Idea.status == IdeaStatus.DRAFT,
                )
                .order_by(Idea.novelty_score.desc().nullslast(), Idea.created_at.asc())
                .limit(1)
            )
            if idea is None:
                return context, "Materialize or generate ranked directions first."
            context["idea_id"] = str(idea.id)
        elif task.agent_type == AgentType.EXPERIMENT_PLANNER.value:
            review = await self.db.scalar(
                select(ReviewDocument).where(ReviewDocument.mission_id == task.mission_id)
            )
            if review is None:
                return context, "Create a literature review document before experiment planning."
            plan = await self.db.scalar(
                select(ExperimentPlan).where(ExperimentPlan.mission_id == task.mission_id)
            )
            context["expected_version"] = plan.version if plan is not None else 0
        elif task.agent_type == AgentType.CODING.value:
            workspace = get_local_workspace_selection(task.project_id)
            isolated = workspace.uses_default and policy.isolated_workspace_confirmed
            context.update(
                {
                    "auto_apply_patch": policy.auto_apply_code and isolated,
                    "isolated_workspace_confirmed": isolated,
                }
            )
            if policy.auto_apply_code and not isolated:
                return context, (
                    "Auto-apply is allowed only in the default isolated project workspace; "
                    "reset the custom workspace or disable auto_apply_code."
                )
        elif task.agent_type == AgentType.EXPERIMENT.value:
            scale = "pilot" if task.task_key == "pilot" else "full"
            run_query = select(ExperimentRun).where(
                ExperimentRun.project_id == task.project_id,
                ExperimentRun.status == ExperimentRunStatus.COMPLETED,
                ExperimentRun.config_json["scale"].astext == scale,
                ExperimentRun.config_json["mission_id"].astext == str(task.mission_id),
                ExperimentRun.config_json["mission_task_id"].astext == str(task.id),
            )
            raw_run_after = task.input_json.get("run_after")
            if raw_run_after:
                try:
                    run_after = datetime.fromisoformat(str(raw_run_after))
                except ValueError:
                    run_after = None
                if run_after is not None:
                    run_query = run_query.where(ExperimentRun.finished_at >= run_after)
            run = await self.db.scalar(
                run_query.order_by(ExperimentRun.finished_at.desc().nullslast()).limit(1)
            )
            if run is None:
                if not policy.allow_trusted_local_execution:
                    return context, (
                        "Approve trusted local execution or use the isolated SSH/container runner."
                    )
                if scale == "pilot" and not policy.pilot_first:
                    return context, "Autopilot requires pilot_first=true before full experiments."
                if scale == "pilot" and policy.pilot_argv:
                    await self._launch_local_experiment(task, actor, policy, scale="pilot")
                    return context, "__runner_started__"
                if scale == "full" and policy.allow_paid_compute and policy.full_argv:
                    await self._launch_local_experiment(task, actor, policy, scale="full")
                    return context, "__runner_started__"
                action = (
                    "Provide a safe pilot command."
                    if scale == "pilot"
                    else "Approve paid/full compute and provide full_argv before scaling."
                )
                return context, action
            context["experiment_run_id"] = str(run.id)
        elif task.agent_type == AgentType.WRITER.value:
            context.update(
                {
                    "venue": policy.venue,
                    "section": ("outline" if task.task_key == "writer_outline" else "results"),
                }
            )
        return context, None

    async def _launch_local_experiment(
        self,
        task: MissionTask,
        actor: User,
        policy: AutopilotStartRequest,
        *,
        scale: str,
    ) -> ExperimentRun:
        experiment = await self.db.scalar(
            select(Experiment)
            .where(
                Experiment.project_id == task.project_id,
                Experiment.name == f"Autopilot {task.mission_id}",
            )
            .limit(1)
        )
        if experiment is None:
            experiment = Experiment(
                project_id=task.project_id,
                name=f"Autopilot {task.mission_id}",
                description="Pilot-first experiments launched by the durable mission coordinator.",
                goal="Produce reproducible receipts for one ranked direction at a time.",
                metric_meta_json={
                    "command_success": {"direction": "max"},
                    "test_pass_rate": {"direction": "max"},
                },
                created_by=actor.id,
            )
            self.db.add(experiment)
            await self.db.flush()
        coding_task = await self.db.scalar(
            select(MissionTask).where(
                MissionTask.mission_id == task.mission_id,
                MissionTask.task_key == "coding",
            )
        )
        commit = (
            str((coding_task.output_json or {}).get("applied_commit_sha") or "")
            if coding_task is not None
            else ""
        ) or None
        argv = policy.pilot_argv if scale == "pilot" else policy.full_argv
        _validate_local_autopilot_argv(argv)
        run = ExperimentRun(
            experiment_id=experiment.id,
            project_id=task.project_id,
            name=f"{scale}-{task.attempt + 1}",
            status=ExperimentRunStatus.QUEUED,
            git_commit=commit,
            command=" ".join(argv),
            config_json={
                "scale": scale,
                "mission_id": str(task.mission_id),
                "mission_task_id": str(task.id),
                "autopilot": True,
                "current_step": f"queued {scale} command",
                "timeout_seconds": (
                    policy.pilot_timeout_seconds
                    if scale == "pilot"
                    else policy.full_timeout_seconds
                ),
            },
            progress=0.0,
            created_by=actor.id,
        )
        self.db.add(run)
        task.status = MissionTaskStatus.RUNNING
        task.attempt += 1
        task.started_at = task.started_at or _now()
        await self.db.flush()
        task.output_json = {
            "experiment_run_id": str(run.id),
            "current_action": f"Running {' '.join(argv)}",
            "scale": scale,
        }
        await self._event(
            task,
            "experiment.local_queued",
            task.output_json,
            actor_id=actor.id,
        )
        await self.db.commit()
        try:
            from researchos.common.celery_app import get_celery_client

            get_celery_client().send_task(
                "experiments.run_local",
                args=[
                    str(run.id),
                    str(task.id),
                    str(actor.id),
                    policy.model_dump(mode="json"),
                ],
                queue="experiments",
            )
        except Exception as exc:  # noqa: BLE001 - durable run remains inspectable
            task.status = MissionTaskStatus.RETRYABLE_FAILED
            task.last_error_json = {
                "code": "experiment_dispatch_failed",
                "message": str(exc)[:500],
            }
            run.status = ExperimentRunStatus.FAILED
            run.finished_at = _now()
            await self.db.commit()
            raise ConflictError("Unable to dispatch the local experiment runner.") from exc
        return run

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
        local_tasks = list(
            (
                await self.db.execute(
                    select(MissionTask).where(
                        MissionTask.mission_id == mission.id,
                        MissionTask.status == MissionTaskStatus.RUNNING,
                        MissionTask.agent_run_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for task in local_tasks:
            raw_run_id = (task.output_json or {}).get("experiment_run_id")
            try:
                run_id = uuid.UUID(str(raw_run_id))
            except (TypeError, ValueError):
                continue
            experiment_run = await self.db.get(ExperimentRun, run_id)
            if experiment_run is None:
                continue
            timeout_seconds = int((experiment_run.config_json or {}).get("timeout_seconds") or 3600)
            stale = bool(
                experiment_run.started_at
                and (now - experiment_run.started_at).total_seconds() > timeout_seconds * 1.25 + 30
            )
            if stale and experiment_run.status == ExperimentRunStatus.RUNNING:
                experiment_run.status = ExperimentRunStatus.FAILED
                experiment_run.finished_at = now
                experiment_run.progress = 100.0
                task.last_error_json = {"code": "local_runner_heartbeat_timeout"}
            if experiment_run.status == ExperimentRunStatus.COMPLETED:
                task.status = MissionTaskStatus.READY
                await self._event(
                    task,
                    "experiment.local_reconciled",
                    {"experiment_run_id": str(experiment_run.id), "status": "completed"},
                    actor_id=actor_id,
                )
                reconciled += 1
            elif experiment_run.status in {
                ExperimentRunStatus.FAILED,
                ExperimentRunStatus.CANCELLED,
            }:
                task.status = (
                    MissionTaskStatus.RETRYABLE_FAILED
                    if task.attempt < task.max_attempts
                    else MissionTaskStatus.TERMINAL_FAILED
                )
                await self._event(
                    task,
                    "experiment.local_reconciled",
                    {
                        "experiment_run_id": str(experiment_run.id),
                        "status": experiment_run.status.value,
                    },
                    actor_id=actor_id,
                )
                reconciled += 1

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
            canonical_output = dict(run.output_json or {})
            produced_artifact = await self._record_artifact(
                task,
                created_by=run.user_id,
                producer_run_id=run.id,
                submission=ArtifactSubmission(
                    schema_name=f"agent-run/{run.agent_type.value}",
                    content_hash=_hash_payload(canonical_output),
                    metadata=canonical_output,
                ),
            )
            await self.db.flush()
            handoff = await self._handoff_envelope(task, run, canonical_output, produced_artifact)
            await self._record_artifact(
                task,
                created_by=run.user_id,
                producer_run_id=run.id,
                submission=ArtifactSubmission(
                    schema_name="researchos.handoff/v1",
                    content_hash=_hash_payload(handoff),
                    metadata=handoff,
                    input_artifact_versions=[
                        {
                            "artifact_id": str(produced_artifact.id),
                            "schema": produced_artifact.schema_name,
                            "version": produced_artifact.schema_version,
                            "sha256": produced_artifact.content_hash,
                        }
                    ],
                ),
            )
            output = {**canonical_output, "handoff": handoff}
            if (
                task.task_key == "coding"
                and bool(output.get("auto_applied"))
                and bool(output.get("applied_commit_sha"))
            ):
                gate = await self.db.scalar(
                    select(ApprovalGate).where(
                        ApprovalGate.task_id == task.id,
                        ApprovalGate.gate_kind == "patch_apply",
                        ApprovalGate.status == ApprovalGateStatus.PENDING,
                    )
                )
                if gate is not None:
                    gate.status = ApprovalGateStatus.APPROVED
                    gate.decided_by = run.user_id
                    gate.decided_at = now
                    gate.decision_json = {
                        "source": "isolated_autopilot",
                        "commit": output.get("applied_commit_sha"),
                    }
            task.output_json = output
            if task.task_key == "read":
                paper_count = int(
                    await self.db.scalar(
                        select(func.count())
                        .select_from(MissionPaper)
                        .where(MissionPaper.mission_id == task.mission_id)
                    )
                    or 0
                )
                card_count = int(
                    await self.db.scalar(
                        select(func.count())
                        .select_from(ReadingCard)
                        .where(ReadingCard.mission_id == task.mission_id)
                    )
                    or 0
                )
                if card_count < paper_count:
                    task.status = MissionTaskStatus.READY
                    task.agent_run_id = None
                    task.output_json = {
                        **output,
                        "paper_count": paper_count,
                        "reading_card_count": card_count,
                        "current_action": f"Extract next paper ({card_count}/{paper_count})",
                    }
                    await self._event(
                        task,
                        "paper_corpus.card_completed",
                        {
                            "agent_run_id": str(run.id),
                            "paper_count": paper_count,
                            "reading_card_count": card_count,
                        },
                        actor_id=actor_id,
                    )
                    return True
            if task.task_key == "code_check" and output.get("verdict") != "pass":
                await self._reset_research_tasks(
                    task,
                    ["coding", "code_check", "pilot", "pilot_review", "leader"],
                    actor_id=actor_id,
                    reason="viewer_requested_code_revision",
                )
                return True
            if task.task_key == "review" and output.get("verdict") != "pass":
                await self._reset_research_tasks(
                    task,
                    ["writer_results", "drawer", "citation", "review"],
                    actor_id=actor_id,
                    reason="viewer_requested_manuscript_revision",
                )
                return True
            if task.task_key == "leader":
                rerouted = await self._route_leader_decision(task, output, actor_id=actor_id)
                if rerouted:
                    return True
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

    async def _handoff_envelope(
        self,
        task: MissionTask,
        run: AgentRun,
        output: dict,
        produced_artifact: TaskArtifact,
    ) -> dict:
        child_rows = (
            await self.db.execute(
                select(MissionTask.task_key, MissionTask.role)
                .join(
                    MissionTaskDependency,
                    MissionTaskDependency.task_id == MissionTask.id,
                )
                .where(MissionTaskDependency.depends_on_task_id == task.id)
                .order_by(MissionTask.priority.asc())
            )
        ).all()
        input_task_ids = list(
            (
                await self.db.execute(
                    select(MissionTaskDependency.depends_on_task_id).where(
                        MissionTaskDependency.task_id == task.id
                    )
                )
            )
            .scalars()
            .all()
        )
        inputs = (
            list(
                (
                    await self.db.execute(
                        select(TaskArtifact).where(TaskArtifact.task_id.in_(input_task_ids))
                    )
                )
                .scalars()
                .all()
            )
            if input_task_ids
            else []
        )
        output_hash = _hash_payload(output)
        return {
            "protocol": "researchos.handoff/v1",
            "message_id": str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{task.id}/{task.attempt}/{output_hash}")
            ),
            "mission_id": str(task.mission_id),
            "task_id": str(task.id),
            "attempt": task.attempt,
            "sender": {
                "kind": "agent",
                "role": task.role,
                "agent_type": run.agent_type.value,
                "run_id": str(run.id),
            },
            "recipients": [{"task_key": task_key, "role": role} for task_key, role in child_rows],
            "type": "artifact_ready",
            "idempotency_key": f"{task.id}/{task.attempt}/{output_hash}",
            "inputs": [
                {
                    "artifact_id": str(artifact.id),
                    "schema": artifact.schema_name,
                    "version": artifact.schema_version,
                    "sha256": artifact.content_hash,
                }
                for artifact in inputs
            ],
            "output": {
                "artifact_id": str(produced_artifact.id),
                "schema": produced_artifact.schema_name,
                "version": produced_artifact.schema_version,
                "sha256": produced_artifact.content_hash,
            },
            "acceptance": list(task.acceptance_json),
            "permissions": list(task.permissions_json),
            "budget": dict(task.budget_json),
            "status": "ready_for_review",
            "error": None,
            "created_at": (run.finished_at or _now()).isoformat(),
        }

    async def _reset_research_tasks(
        self,
        source_task: MissionTask,
        task_keys: list[str],
        *,
        actor_id: uuid.UUID | None,
        reason: str,
    ) -> None:
        rows = list(
            (
                await self.db.execute(
                    select(MissionTask)
                    .where(
                        MissionTask.mission_id == source_task.mission_id,
                        MissionTask.task_key.in_(task_keys),
                    )
                    .order_by(MissionTask.priority.asc())
                )
            )
            .scalars()
            .all()
        )
        by_key = {row.task_key: row for row in rows}
        first = by_key.get(task_keys[0])
        if first is None:
            raise NotFoundError(f"Cannot reroute missing task: {task_keys[0]}")
        if first.attempt >= first.max_attempts:
            first.status = MissionTaskStatus.TERMINAL_FAILED
            first.last_error_json = {
                "code": "research_revision_budget_exhausted",
                "reason": reason,
            }
            source_task.status = MissionTaskStatus.TERMINAL_FAILED
            source_task.last_error_json = first.last_error_json
            return
        now = _now()
        for index, key in enumerate(task_keys):
            row = by_key.get(key)
            if row is None:
                continue
            history = list(row.input_json.get("attempt_history") or [])
            if row.output_json:
                history.append(
                    {
                        "attempt": row.attempt,
                        "output_hash": _hash_payload(row.output_json),
                        "status": row.status,
                    }
                )
            row.input_json = {
                **row.input_json,
                "attempt_history": history[-20:],
                "reroute_reason": reason,
                "run_after": now.isoformat() if key in {"pilot", "experiment_run"} else None,
            }
            row.status = MissionTaskStatus.READY if index == 0 else MissionTaskStatus.DRAFT
            row.agent_run_id = None
            row.output_json = {}
            row.last_error_json = None
            row.started_at = None
            row.finished_at = None
        for gate in list(
            (
                await self.db.execute(
                    select(ApprovalGate).where(
                        ApprovalGate.mission_id == source_task.mission_id,
                        ApprovalGate.task_id.in_([row.id for row in rows]),
                    )
                )
            )
            .scalars()
            .all()
        ):
            if gate.gate_kind in {"patch_apply", "repository_import", "compute"}:
                gate.status = ApprovalGateStatus.PENDING
                gate.decided_by = None
                gate.decided_at = None
                gate.decision_json = {}
        await self._event(
            source_task,
            "research_loop.rerouted",
            {"reason": reason, "next_task": task_keys[0], "reset_tasks": task_keys},
            actor_id=actor_id,
        )

    async def _route_leader_decision(
        self,
        task: MissionTask,
        output: dict,
        *,
        actor_id: uuid.UUID | None,
    ) -> bool:
        decision = str(output.get("decision") or "stop")
        if decision in {"scale_experiments", "write"}:
            return False
        if decision == "stop":
            task.status = MissionTaskStatus.COMPLETED
            task.finished_at = _now()
            downstream = list(
                (
                    await self.db.execute(
                        select(MissionTask).where(
                            MissionTask.mission_id == task.mission_id,
                            MissionTask.priority > task.priority,
                            MissionTask.status.in_(
                                [MissionTaskStatus.DRAFT, MissionTaskStatus.READY]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for item in downstream:
                item.status = MissionTaskStatus.CANCELLED
                item.finished_at = _now()
            await self._event(
                task,
                "research_loop.stopped",
                {"reason": output.get("rationale"), "cancelled": len(downstream)},
                actor_id=actor_id,
            )
            return True
        if decision == "continue_pilot":
            await self._reset_research_tasks(
                task,
                ["pilot", "pilot_review", "leader"],
                actor_id=actor_id,
                reason="leader_requested_additional_pilot",
            )
            return True
        if decision == "revise_code":
            await self._reset_research_tasks(
                task,
                ["coding", "code_check", "pilot", "pilot_review", "leader"],
                actor_id=actor_id,
                reason="leader_requested_code_revision",
            )
            return True
        if decision == "try_direction":
            policy = dict(task.input_json.get("autopilot_policy") or {})
            max_directions = min(10, max(1, int(policy.get("max_directions") or 10)))
            mission_ideas = list(
                (
                    await self.db.execute(
                        select(Idea).where(
                            Idea.project_id == task.project_id,
                            Idea.metadata_json["mission_id"].astext == str(task.mission_id),
                        )
                    )
                )
                .scalars()
                .all()
            )
            tried = sum(
                idea.status in {IdeaStatus.ACTIVE, IdeaStatus.ARCHIVED} for idea in mission_ideas
            )
            if tried >= max_directions:
                output["decision"] = "stop"
                output["rationale"] = "Top-direction attempt budget exhausted."
                return await self._route_leader_decision(task, output, actor_id=actor_id)
            for idea in mission_ideas:
                if idea.status == IdeaStatus.ACTIVE:
                    idea.status = IdeaStatus.ARCHIVED
            await self._reset_research_tasks(
                task,
                [
                    "critic",
                    "direction",
                    "repository",
                    "baseline",
                    "coding",
                    "code_check",
                    "pilot",
                    "pilot_review",
                    "leader",
                ],
                actor_id=actor_id,
                reason="leader_selected_next_ranked_direction",
            )
            return True
        raise ValidationError(f"Unsupported Leader decision: {decision}")

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

    async def _promote_dependents(self, task: MissionTask, *, actor_id: uuid.UUID | None) -> int:
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
        input_artifacts = await self._dependency_artifacts(task)
        run_context = {
            **task.input_json,
            **context,
            "mission_task_id": str(task.id),
            "input_artifacts": input_artifacts,
        }
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

    async def _dependency_artifacts(self, task: MissionTask) -> list[dict]:
        dependencies = list(
            (
                await self.db.execute(
                    select(MissionTaskDependency).where(MissionTaskDependency.task_id == task.id)
                )
            )
            .scalars()
            .all()
        )
        artifacts: list[dict] = []
        for dependency in dependencies:
            rows = list(
                (
                    await self.db.execute(
                        select(TaskArtifact)
                        .where(TaskArtifact.task_id == dependency.depends_on_task_id)
                        .order_by(TaskArtifact.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            if dependency.required_artifact_schema:
                rows = [
                    row for row in rows if row.schema_name == dependency.required_artifact_schema
                ]
                if not rows:
                    raise ConflictError(
                        f"Dependency artifact is missing: {dependency.required_artifact_schema}",
                        code="dependency_artifact_missing",
                    )
            artifacts.extend(
                {
                    "artifact_id": str(row.id),
                    "schema": row.schema_name,
                    "version": row.schema_version,
                    "sha256": row.content_hash,
                    "uri": row.uri,
                    "metadata": row.metadata_json,
                }
                for row in rows[:10]
            )
        return artifacts[:50]

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
        await self.db.refresh(task)
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
