"""Mission experiment-plan editing, evidence checks, versioning, and publication."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.experiments.models import Experiment
from researchos.identity.models import User
from researchos.knowledge.models import MissionPaper
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.projects.service import ProjectService
from researchos.research.models import PaperSection

from .models import ExperimentPlan, ExperimentPlanVersion
from .schemas import GenerateExperimentPlanRequest, UpsertExperimentPlanRequest


class ExperimentPlanService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _mission(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID, *, write: bool
    ) -> ResearchMission:
        await ProjectService(self.db).ensure_access(
            actor, project_id, ProjectRole.RESEARCHER if write else ProjectRole.VIEWER
        )
        mission = await self.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != project_id:
            raise NotFoundError("Research mission not found.")
        return mission

    async def get(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> ExperimentPlan:
        await self._mission(actor, project_id, mission_id, write=False)
        plan = await self.db.scalar(
            select(ExperimentPlan).where(ExperimentPlan.mission_id == mission_id)
        )
        if plan is None:
            raise NotFoundError("Experiment plan not found.")
        return plan

    async def upsert(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: UpsertExperimentPlanRequest,
    ) -> ExperimentPlan:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        plan = await self.db.scalar(
            select(ExperimentPlan).where(ExperimentPlan.mission_id == mission_id)
        )
        if plan is None:
            if payload.expected_version is not None:
                raise ConflictError(
                    "Experiment plan does not exist yet.", code="experiment_plan_version_conflict"
                )
            plan = ExperimentPlan(
                project_id=project_id,
                mission_id=mission_id,
                title=payload.title,
                created_by=actor.id,
                updated_by=actor.id,
            )
            self.db.add(plan)
        else:
            if payload.expected_version != plan.version:
                raise ConflictError(
                    "Experiment plan changed elsewhere.", code="experiment_plan_version_conflict"
                )
            plan.version += 1
        await self._validate_baselines(mission_id, payload.baselines)
        data = payload.model_dump(mode="json", exclude={"expected_version"})
        for name in (
            "title",
            "research_gap",
            "hypothesis",
            "status",
        ):
            setattr(plan, name, data[name])
        for name in (
            "variables",
            "baselines",
            "datasets",
            "metrics",
            "matrix",
            "decision_rules",
            "stop_conditions",
            "risks",
            "reproducibility",
        ):
            setattr(plan, f"{name}_json", data[name])
        plan.updated_by = actor.id
        await record_plan_version(self.db, plan, actor.id, "human")
        mission.last_activity_at = datetime.now(tz=UTC)
        mission.updated_by = actor.id
        self.db.add(
            MissionEvent(
                project_id=project_id,
                mission_id=mission_id,
                event_type="experiment_plan.saved",
                summary=f"保存结构化实验方案 v{plan.version}",
                step_kind=mission.current_step,
                payload_json={"plan_id": str(plan.id), "version": plan.version},
                actor_id=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def validate_generation(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: GenerateExperimentPlanRequest,
    ) -> ExperimentPlan | None:
        await self._mission(actor, project_id, mission_id, write=True)
        plan = await self.db.scalar(
            select(ExperimentPlan).where(ExperimentPlan.mission_id == mission_id)
        )
        actual = plan.version if plan is not None else 0
        if actual != payload.expected_version:
            raise ConflictError(
                "Experiment plan changed elsewhere.", code="experiment_plan_version_conflict"
            )
        if plan is not None and not payload.regenerate:
            raise ConflictError(
                "An experiment plan already exists. Confirm regeneration to replace it.",
                code="experiment_plan_regeneration_confirmation_required",
            )
        return plan

    async def versions(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[ExperimentPlanVersion]:
        plan = await self.get(actor, project_id, mission_id)
        return list(
            (
                await self.db.execute(
                    select(ExperimentPlanVersion)
                    .where(ExperimentPlanVersion.plan_id == plan.id)
                    .order_by(ExperimentPlanVersion.version.desc())
                )
            )
            .scalars()
            .all()
        )

    async def publish(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> tuple[ExperimentPlan, Experiment]:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        plan = await self.db.scalar(
            select(ExperimentPlan).where(ExperimentPlan.mission_id == mission_id)
        )
        if plan is None:
            raise NotFoundError("Experiment plan not found.")
        if plan.published_experiment_id is not None:
            experiment = await self.db.get(Experiment, plan.published_experiment_id)
            if experiment is not None:
                return plan, experiment
        issues = publish_issues(plan)
        if issues:
            raise ValidationError("Plan is not publishable: " + "; ".join(issues))
        experiment = Experiment(
            project_id=project_id,
            name=plan.title,
            description=plan.research_gap,
            goal=plan.hypothesis,
            default_config_json={
                "mission_id": str(mission_id),
                "plan_version": plan.version,
                "variables": plan.variables_json,
                "datasets": plan.datasets_json,
                "matrix": plan.matrix_json,
                "decision_rules": plan.decision_rules_json,
                "stop_conditions": plan.stop_conditions_json,
                "reproducibility": plan.reproducibility_json,
            },
            metric_meta_json={
                item["name"]: {
                    "direction": item["direction"],
                    "unit": item.get("unit") or None,
                    "primary": bool(item.get("primary")),
                }
                for item in plan.metrics_json
            },
            created_by=actor.id,
        )
        self.db.add(experiment)
        await self.db.flush()
        plan.version += 1
        plan.status = "published"
        plan.published_experiment_id = experiment.id
        plan.updated_by = actor.id
        await record_plan_version(self.db, plan, actor.id, "publish")
        mission.last_activity_at = datetime.now(tz=UTC)
        mission.updated_by = actor.id
        self.db.add(
            MissionEvent(
                project_id=project_id,
                mission_id=mission_id,
                event_type="experiment_plan.published",
                summary=f"实验方案已发布到实验面板：{plan.title}",
                step_kind=mission.current_step,
                payload_json={
                    "plan_id": str(plan.id),
                    "plan_version": plan.version,
                    "experiment_id": str(experiment.id),
                },
                actor_id=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(plan)
        return plan, experiment

    async def _validate_baselines(self, mission_id: uuid.UUID, baselines: list) -> None:
        allowed = set(
            (
                await self.db.execute(
                    select(MissionPaper.paper_id).where(MissionPaper.mission_id == mission_id)
                )
            )
            .scalars()
            .all()
        )
        for item in baselines:
            if item.source_paper_id is not None and item.source_paper_id not in allowed:
                raise ValidationError("Baseline evidence must reference a mission paper.")
            if item.evidence_status != "grounded":
                continue
            if not item.source_paper_id or not item.evidence_section_id or not item.evidence_quote:
                raise ValidationError(
                    "Grounded baseline evidence requires paper, section, and quote."
                )
            section = await self.db.get(PaperSection, item.evidence_section_id)
            if (
                section is None
                or section.paper_id != item.source_paper_id
                or item.evidence_quote not in section.body
            ):
                raise ValidationError("Grounded baseline quote was not found in the parsed source.")


async def record_plan_version(
    db: AsyncSession,
    plan: ExperimentPlan,
    actor_id: uuid.UUID,
    source_type: str,
    source_run_id: uuid.UUID | None = None,
) -> None:
    await db.flush()
    snapshot = {
        "title": plan.title,
        "research_gap": plan.research_gap,
        "hypothesis": plan.hypothesis,
        "variables": plan.variables_json,
        "baselines": plan.baselines_json,
        "datasets": plan.datasets_json,
        "metrics": plan.metrics_json,
        "matrix": plan.matrix_json,
        "decision_rules": plan.decision_rules_json,
        "stop_conditions": plan.stop_conditions_json,
        "risks": plan.risks_json,
        "reproducibility": plan.reproducibility_json,
        "status": plan.status,
        "published_experiment_id": (
            str(plan.published_experiment_id) if plan.published_experiment_id else None
        ),
    }
    db.add(
        ExperimentPlanVersion(
            project_id=plan.project_id,
            mission_id=plan.mission_id,
            plan_id=plan.id,
            version=plan.version,
            snapshot_json=snapshot,
            source_type=source_type,
            source_run_id=source_run_id,
            created_by=actor_id,
        )
    )
    await db.flush()


def publish_issues(plan: ExperimentPlan) -> list[str]:
    issues: list[str] = []
    if not plan.hypothesis.strip():
        issues.append("hypothesis is empty")
    roles = {item.get("role") for item in plan.variables_json}
    for role in ("independent", "dependent", "control"):
        if role not in roles:
            issues.append(f"missing {role} variable")
    if not plan.baselines_json:
        issues.append("no baseline")
    elif any(item.get("evidence_status") != "grounded" for item in plan.baselines_json):
        issues.append("baseline evidence is unresolved")
    if not plan.datasets_json:
        issues.append("no dataset or data source")
    if not any(item.get("primary") for item in plan.metrics_json):
        issues.append("no primary metric")
    if not plan.matrix_json:
        issues.append("experiment matrix is empty")
    if not plan.decision_rules_json:
        issues.append("decision rule is empty")
    if not plan.stop_conditions_json:
        issues.append("stop condition is empty")
    if not plan.risks_json:
        issues.append("risk register is empty")
    return issues
