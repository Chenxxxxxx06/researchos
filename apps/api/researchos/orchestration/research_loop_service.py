"""Bounded candidate experiment loops linked to the durable mission DAG."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.models import AgentRun
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.experiments.directions import dedupe_points, reduce_series
from researchos.experiments.enums import ExperimentRunStatus
from researchos.experiments.models import ExperimentMetric, ExperimentRun
from researchos.figures.enums import AnchorAggregation
from researchos.identity.models import User
from researchos.missions.models import ResearchMission
from researchos.patches.enums import PatchStatus
from researchos.patches.models import PatchFile, PatchProposal
from researchos.projects.service import ProjectService

from .enums import MissionTaskStatus, ResearchIterationStatus, ResearchLoopStatus
from .loop_policy import evaluate_candidate, normalize_scopes, stop_reason, validate_changed_paths
from .models import MissionTask, ResearchLoop, ResearchLoopIteration
from .schemas import (
    ArtifactSubmission,
    ResearchIterationCreateRequest,
    ResearchIterationEvaluateRequest,
    ResearchLoopControlRequest,
    ResearchLoopCreateRequest,
    ResearchLoopIterationResponse,
    ResearchLoopResponse,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _hash_payload(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class ResearchLoopService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def list_loops(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[ResearchLoopResponse]:
        await self._mission(actor, project_id, mission_id, write=False)
        loops = list(
            (
                await self.db.execute(
                    select(ResearchLoop)
                    .where(ResearchLoop.mission_id == mission_id)
                    .order_by(ResearchLoop.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [await self._response(loop) for loop in loops]

    async def create_loop(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: ResearchLoopCreateRequest,
    ) -> ResearchLoopResponse:
        await self._mission(actor, project_id, mission_id, write=True)
        task = await self.db.scalar(
            select(MissionTask)
            .where(
                MissionTask.mission_id == mission_id,
                MissionTask.task_key == "experiment_run",
            )
            .with_for_update()
        )
        if task is None:
            raise ConflictError("Initialize the mission Agent DAG before starting a research loop.")
        if task.status != MissionTaskStatus.READY:
            raise ConflictError("The experiment-run task must be ready before starting a loop.")
        active = await self.db.scalar(
            select(ResearchLoop.id).where(
                ResearchLoop.task_id == task.id,
                ResearchLoop.status.in_([ResearchLoopStatus.ACTIVE, ResearchLoopStatus.PAUSED]),
            )
        )
        if active is not None:
            raise ConflictError("This mission already has an active research loop.")
        baseline = await self._completed_run(project_id, payload.baseline_run_id)
        if not baseline.git_commit:
            raise ValidationError("The baseline run must record its Git commit.")
        metric = await self._metric_value(
            baseline.id,
            payload.metric_name,
            payload.metric_direction,
            payload.metric_aggregation,
        )
        editable = normalize_scopes(payload.editable_scopes)
        protected = (
            normalize_scopes(payload.protected_scopes) if payload.protected_scopes else []
        )
        loop = ResearchLoop(
            project_id=project_id,
            mission_id=mission_id,
            task_id=task.id,
            name=payload.name,
            status=ResearchLoopStatus.ACTIVE,
            metric_name=payload.metric_name,
            metric_direction=payload.metric_direction,
            metric_aggregation=payload.metric_aggregation,
            baseline_run_id=baseline.id,
            best_run_id=baseline.id,
            baseline_metric_value=metric,
            best_metric_value=metric,
            fixed_budget_seconds=payload.fixed_budget_seconds,
            max_iterations=payload.max_iterations,
            patience=payload.patience,
            min_delta=payload.min_delta,
            max_complexity_delta=payload.max_complexity_delta,
            critic_threshold=payload.critic_threshold,
            editable_scope_json=editable,
            protected_scope_json=protected,
            created_by=actor.id,
        )
        self.db.add(loop)
        task.status = MissionTaskStatus.RUNNING
        task.attempt += 1
        task.started_at = task.started_at or _now()
        await self.db.flush()
        await self._coordinator_event(
            task,
            "research_loop.started",
            {
                "loop_id": str(loop.id),
                "baseline_run_id": str(baseline.id),
                "metric": payload.metric_name,
                "baseline": metric,
            },
            actor.id,
        )
        await self.db.commit()
        return await self._response(loop)

    async def create_iteration(
        self,
        actor: User,
        project_id: uuid.UUID,
        loop_id: uuid.UUID,
        payload: ResearchIterationCreateRequest,
    ) -> ResearchLoopResponse:
        loop = await self._locked_loop(actor, project_id, loop_id)
        if loop.status != ResearchLoopStatus.ACTIVE:
            raise ConflictError("Only an active research loop accepts new iterations.")
        if loop.current_iteration >= loop.max_iterations:
            raise ConflictError("The research loop exhausted its iteration budget.")
        open_iteration = await self.db.scalar(
            select(ResearchLoopIteration.id).where(
                ResearchLoopIteration.loop_id == loop.id,
                ResearchLoopIteration.status.in_(
                    [ResearchIterationStatus.PROPOSED, ResearchIterationStatus.RUNNING]
                ),
            )
        )
        if open_iteration is not None:
            raise ConflictError("Evaluate the current iteration before proposing another one.")
        changed_paths = validate_changed_paths(
            payload.changed_paths,
            editable_scopes=loop.editable_scope_json,
            protected_scopes=loop.protected_scope_json,
        )
        if payload.agent_run_id is not None:
            run = await self.db.get(AgentRun, payload.agent_run_id)
            if run is None or run.project_id != project_id:
                raise ValidationError("Agent run does not belong to this project.")
        number = loop.current_iteration + 1
        iteration = ResearchLoopIteration(
            loop_id=loop.id,
            project_id=project_id,
            mission_id=loop.mission_id,
            task_id=loop.task_id,
            iteration_number=number,
            status=ResearchIterationStatus.PROPOSED,
            hypothesis=payload.hypothesis,
            component=payload.component,
            expected_effect=payload.expected_effect,
            changed_paths_json=changed_paths,
            agent_run_id=payload.agent_run_id,
            started_at=_now(),
            created_by=actor.id,
        )
        self.db.add(iteration)
        loop.current_iteration = number
        await self.db.flush()
        task = await self.db.get(MissionTask, loop.task_id)
        if task is not None:
            await self._coordinator_event(
                task,
                "research_loop.iteration_proposed",
                {
                    "loop_id": str(loop.id),
                    "iteration_id": str(iteration.id),
                    "iteration": number,
                    "component": payload.component,
                },
                actor.id,
            )
        await self.db.commit()
        return await self._response(loop)

    async def evaluate_iteration(
        self,
        actor: User,
        project_id: uuid.UUID,
        iteration_id: uuid.UUID,
        payload: ResearchIterationEvaluateRequest,
    ) -> ResearchLoopResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        iteration = await self.db.scalar(
            select(ResearchLoopIteration)
            .where(
                ResearchLoopIteration.id == iteration_id,
                ResearchLoopIteration.project_id == project_id,
            )
            .with_for_update()
        )
        if iteration is None:
            raise NotFoundError("Research loop iteration not found.")
        if iteration.status not in {
            ResearchIterationStatus.PROPOSED,
            ResearchIterationStatus.RUNNING,
        }:
            raise ConflictError("This research iteration has already been evaluated.")
        loop = await self.db.scalar(
            select(ResearchLoop).where(ResearchLoop.id == iteration.loop_id).with_for_update()
        )
        if loop is None or loop.status != ResearchLoopStatus.ACTIVE:
            raise ConflictError("The research loop is not active.")
        run = await self.db.get(ExperimentRun, payload.experiment_run_id)
        if run is None or run.project_id != project_id:
            raise ValidationError("Experiment run does not belong to this project.")
        iteration.experiment_run_id = run.id
        iteration.complexity_delta = payload.complexity_delta
        iteration.critic_score = payload.critic_score
        iteration.code_commit_sha = run.git_commit
        checks = dict(payload.rule_checks)
        if run.status in {ExperimentRunStatus.FAILED, ExperimentRunStatus.CANCELLED}:
            await self._record_crash(actor, loop, iteration, run, checks)
            return await self._finish_evaluation(loop, iteration, actor)
        if run.status != ExperimentRunStatus.COMPLETED:
            raise ConflictError("Only a terminal experiment run can be evaluated.")

        elapsed = self._elapsed_seconds(run)
        checks["completed_within_fixed_budget"] = (
            elapsed is not None and elapsed <= loop.fixed_budget_seconds * 1.1
        )
        checks["git_commit_recorded"] = bool(run.git_commit)
        checks["change_traceable"] = await self._validate_change_binding(
            project_id, loop, iteration, run, payload.patch_id
        )
        metric = await self._metric_value(
            run.id,
            loop.metric_name,
            loop.metric_direction,
            loop.metric_aggregation,
        )
        decision = evaluate_candidate(
            direction=loop.metric_direction,  # type: ignore[arg-type]
            incumbent=loop.best_metric_value,
            candidate=metric,
            min_delta=loop.min_delta,
            complexity_delta=payload.complexity_delta,
            max_complexity_delta=loop.max_complexity_delta,
            critic_score=payload.critic_score,
            critic_threshold=loop.critic_threshold,
            rule_checks=checks,
        )
        iteration.metric_value = metric
        iteration.improvement = decision.improvement
        iteration.rule_checks_json = checks
        iteration.decision_json = {
            "decision": decision.status,
            "reasons": list(decision.reasons),
            "simplicity_win": decision.simplicity_win,
            "incumbent_metric": loop.best_metric_value,
        }
        iteration.status = (
            ResearchIterationStatus.KEPT
            if decision.status == "kept"
            else ResearchIterationStatus.DISCARDED
        )
        iteration.finished_at = _now()
        if decision.status == "kept":
            loop.best_metric_value = metric
            loop.best_run_id = run.id
            loop.no_improvement_count = 0
        else:
            loop.no_improvement_count += 1
        return await self._finish_evaluation(loop, iteration, actor)

    async def control(
        self,
        actor: User,
        project_id: uuid.UUID,
        loop_id: uuid.UUID,
        payload: ResearchLoopControlRequest,
    ) -> ResearchLoopResponse:
        loop = await self._locked_loop(actor, project_id, loop_id)
        if payload.action == "pause":
            if loop.status != ResearchLoopStatus.ACTIVE:
                raise ConflictError("Only an active research loop can be paused.")
            loop.status = ResearchLoopStatus.PAUSED
            loop.stop_reason = payload.reason or "paused_by_user"
        elif payload.action == "resume":
            if loop.status != ResearchLoopStatus.PAUSED:
                raise ConflictError("Only a paused research loop can be resumed.")
            loop.status = ResearchLoopStatus.ACTIVE
            loop.stop_reason = None
        elif payload.action == "finalize":
            if loop.status not in {ResearchLoopStatus.ACTIVE, ResearchLoopStatus.PAUSED}:
                raise ConflictError("This research loop is already terminal.")
            await self._finalize_loop(loop, actor.id, payload.reason or "finalized_by_user")
        else:
            if loop.status not in {ResearchLoopStatus.ACTIVE, ResearchLoopStatus.PAUSED}:
                raise ConflictError("This research loop is already terminal.")
            loop.status = ResearchLoopStatus.CANCELLED
            loop.stop_reason = payload.reason or "cancelled_by_user"
            task = await self.db.get(MissionTask, loop.task_id)
            if task is not None:
                task.status = MissionTaskStatus.CANCELLED
                task.finished_at = _now()
        await self.db.commit()
        return await self._response(loop)

    async def _finish_evaluation(
        self, loop: ResearchLoop, iteration: ResearchLoopIteration, actor: User
    ) -> ResearchLoopResponse:
        task = await self.db.get(MissionTask, loop.task_id)
        if task is None:
            raise NotFoundError("Mission task not found.")
        payload = {
            "loop_id": str(loop.id),
            "iteration_id": str(iteration.id),
            "iteration": iteration.iteration_number,
            "status": iteration.status,
            "metric": iteration.metric_value,
            "improvement": iteration.improvement,
            "decision": iteration.decision_json,
        }
        await self._coordinator_artifact(task, actor.id, payload)
        await self._coordinator_event(task, "research_loop.iteration_evaluated", payload, actor.id)
        reason = stop_reason(
            iteration_count=loop.current_iteration,
            no_improvement_count=loop.no_improvement_count,
            max_iterations=loop.max_iterations,
            patience=loop.patience,
        )
        if reason:
            await self._finalize_loop(loop, actor.id, reason)
        await self.db.commit()
        return await self._response(loop)

    async def _record_crash(
        self,
        actor: User,
        loop: ResearchLoop,
        iteration: ResearchLoopIteration,
        run: ExperimentRun,
        checks: dict[str, bool],
    ) -> None:
        iteration.status = ResearchIterationStatus.CRASHED
        iteration.rule_checks_json = {**checks, "experiment_completed": False}
        iteration.decision_json = {
            "decision": "crashed",
            "reasons": [f"experiment_{run.status.value}"],
        }
        iteration.finished_at = _now()
        loop.no_improvement_count += 1

    async def _finalize_loop(
        self, loop: ResearchLoop, actor_id: uuid.UUID, reason: str
    ) -> None:
        loop.status = ResearchLoopStatus.COMPLETED
        loop.stop_reason = reason
        task = await self.db.get(MissionTask, loop.task_id)
        if task is None:
            raise NotFoundError("Mission task not found.")
        task.status = MissionTaskStatus.COMPLETED
        task.finished_at = _now()
        task.output_json = {
            "research_loop_id": str(loop.id),
            "best_run_id": str(loop.best_run_id),
            "baseline_metric": loop.baseline_metric_value,
            "best_metric": loop.best_metric_value,
            "metric_name": loop.metric_name,
            "stop_reason": reason,
        }
        await self._coordinator_artifact(task, actor_id, task.output_json, final=True)
        await self._coordinator_event(
            task,
            "research_loop.completed",
            task.output_json,
            actor_id,
        )
        from .service import OrchestrationService

        await OrchestrationService(self.db)._promote_dependents(task, actor_id=actor_id)

    async def _validate_change_binding(
        self,
        project_id: uuid.UUID,
        loop: ResearchLoop,
        iteration: ResearchLoopIteration,
        run: ExperimentRun,
        patch_id: uuid.UUID | None,
    ) -> bool:
        if patch_id is None:
            return str(run.config_json.get("research_loop_iteration_id", "")) == str(iteration.id)
        patch = await self.db.get(PatchProposal, patch_id)
        if patch is None or patch.project_id != project_id or patch.status != PatchStatus.APPLIED:
            return False
        paths = list(
            (
                await self.db.execute(select(PatchFile.path).where(PatchFile.patch_id == patch.id))
            )
            .scalars()
            .all()
        )
        try:
            normalized = validate_changed_paths(
                paths,
                editable_scopes=loop.editable_scope_json,
                protected_scopes=loop.protected_scope_json,
            )
        except ValidationError:
            return False
        iteration.patch_id = patch.id
        return (
            set(normalized) == set(iteration.changed_paths_json)
            and bool(patch.applied_commit_sha)
            and patch.applied_commit_sha == run.git_commit
        )

    async def _metric_value(
        self,
        run_id: uuid.UUID,
        metric_name: str,
        direction: str,
        aggregation: str,
    ) -> float:
        rows = list(
            (
                await self.db.execute(
                    select(ExperimentMetric).where(
                        ExperimentMetric.run_id == run_id,
                        ExperimentMetric.name == metric_name,
                    )
                )
            )
            .scalars()
            .all()
        )
        value = reduce_series(
            dedupe_points(rows),
            aggregation=(
                AnchorAggregation.BEST if aggregation == "best" else AnchorAggregation.FINAL
            ),
            direction=direction,  # type: ignore[arg-type]
        )
        if value is None:
            raise ValidationError(f"Experiment run has no metric named '{metric_name}'.")
        return value

    async def _completed_run(
        self, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> ExperimentRun:
        run = await self.db.get(ExperimentRun, run_id)
        if (
            run is None
            or run.project_id != project_id
            or run.status != ExperimentRunStatus.COMPLETED
        ):
            raise ValidationError("The baseline must be a completed project experiment run.")
        return run

    async def _locked_loop(
        self, actor: User, project_id: uuid.UUID, loop_id: uuid.UUID
    ) -> ResearchLoop:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        loop = await self.db.scalar(
            select(ResearchLoop)
            .where(ResearchLoop.id == loop_id, ResearchLoop.project_id == project_id)
            .with_for_update()
        )
        if loop is None:
            raise NotFoundError("Research loop not found.")
        return loop

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

    async def _response(self, loop: ResearchLoop) -> ResearchLoopResponse:
        # Database-managed timestamps may be expired after an UPDATE. Refresh
        # explicitly so response validation never attempts implicit async IO.
        await self.db.refresh(loop)
        iterations = list(
            (
                await self.db.execute(
                    select(ResearchLoopIteration)
                    .where(ResearchLoopIteration.loop_id == loop.id)
                    .order_by(ResearchLoopIteration.iteration_number.asc())
                )
            )
            .scalars()
            .all()
        )
        response = ResearchLoopResponse.model_validate(loop)
        return response.model_copy(
            update={
                "iterations": [
                    ResearchLoopIterationResponse.model_validate(item) for item in iterations
                ]
            }
        )

    async def _coordinator_event(
        self, task: MissionTask, event_type: str, payload: dict, actor_id: uuid.UUID
    ) -> None:
        from .service import OrchestrationService

        await OrchestrationService(self.db)._event(
            task, event_type, payload, actor_id=actor_id
        )

    async def _coordinator_artifact(
        self, task: MissionTask, actor_id: uuid.UUID, payload: dict, *, final: bool = False
    ) -> None:
        from .service import OrchestrationService

        await OrchestrationService(self.db)._record_artifact(
            task,
            created_by=actor_id,
            producer_run_id=None,
            submission=ArtifactSubmission(
                schema_name=(
                    "research-loop-result/v1" if final else "research-loop-iteration/v1"
                ),
                content_hash=_hash_payload(payload),
                metadata=payload,
            ),
        )

    @staticmethod
    def _elapsed_seconds(run: ExperimentRun) -> float | None:
        if run.started_at is None or run.finished_at is None:
            return None
        return max(0.0, (run.finished_at - run.started_at).total_seconds())
