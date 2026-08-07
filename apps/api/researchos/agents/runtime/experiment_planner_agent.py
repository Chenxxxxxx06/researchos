"""Evidence-bound experiment planning agent."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.experiment_plans.models import ExperimentPlan
from researchos.experiment_plans.schemas import UpsertExperimentPlanRequest
from researchos.experiment_plans.service import ExperimentPlanService, record_plan_version
from researchos.knowledge.models import MissionPaper
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.research.models import Paper, PaperSection
from researchos.reviews.models import ReviewDocument, ReviewSection

from .base import Agent, AgentContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "research_gap": {"type": "string"},
        "hypothesis": {"type": "string"},
        "variables": {"type": "array", "items": {"type": "object"}},
        "baselines": {"type": "array", "items": {"type": "object"}},
        "datasets": {"type": "array", "items": {"type": "object"}},
        "metrics": {"type": "array", "items": {"type": "object"}},
        "matrix": {"type": "array", "items": {"type": "object"}},
        "decision_rules": {"type": "array", "items": {"type": "string"}},
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "object"}},
        "reproducibility": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "research_gap",
        "hypothesis",
        "variables",
        "baselines",
        "datasets",
        "metrics",
        "matrix",
        "decision_rules",
        "stop_conditions",
        "risks",
        "reproducibility",
    ],
}

_SYSTEM = """You design a falsifiable and reproducible experiment from a mission review.
Use only supplied review text and parsed paper evidence. Include independent, dependent, and control
variables; a baseline; data split; at least one primary metric; experiment matrix; decision and stop
rules; risks; and reproducibility controls. A grounded baseline must cite exact paper UUID,
section UUID, and verbatim quote. Otherwise mark it needs_evidence. Return only the requested
JSON object."""


class ExperimentPlannerAgent(Agent):
    agent_type = AgentType.EXPERIMENT_PLANNER
    allowed_tools: list[str] = []
    response_schema = _SCHEMA

    async def _context(
        self, actx: AgentContext
    ) -> tuple[ResearchMission, ExperimentPlan | None, list[ReviewSection], list[PaperSection]]:
        try:
            mission_id = uuid.UUID(str(actx.context["mission_id"]))
            expected_version = int(actx.context["expected_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                "Experiment-planner runs require mission_id and expected_version."
            ) from exc
        mission = await actx.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != actx.project_id:
            raise NotFoundError("Research mission not found for experiment planning.")
        plan = await actx.db.scalar(
            select(ExperimentPlan).where(ExperimentPlan.mission_id == mission.id)
        )
        if (plan.version if plan is not None else 0) != expected_version:
            raise ConflictError(
                "Experiment plan changed after generation was requested.",
                code="experiment_plan_version_conflict",
            )
        review = await actx.db.scalar(
            select(ReviewDocument).where(ReviewDocument.mission_id == mission.id)
        )
        if review is None:
            raise ValidationError(
                "Generate and review the literature outline before experiment planning."
            )
        review_sections = list(
            (
                await actx.db.execute(
                    select(ReviewSection)
                    .where(ReviewSection.review_id == review.id)
                    .order_by(ReviewSection.position)
                )
            )
            .scalars()
            .all()
        )
        paper_ids = list(
            (
                await actx.db.execute(
                    select(MissionPaper.paper_id).where(MissionPaper.mission_id == mission.id)
                )
            )
            .scalars()
            .all()
        )
        sources = list(
            (
                await actx.db.execute(
                    select(PaperSection)
                    .where(PaperSection.paper_id.in_(paper_ids))
                    .order_by(PaperSection.paper_id, PaperSection.seq)
                )
            )
            .scalars()
            .all()
        )
        return mission, plan, review_sections, sources

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        mission, _plan, review_sections, sources = await self._context(actx)
        paper_ids = {source.paper_id for source in sources}
        papers = list(
            (
                await actx.db.execute(
                    select(Paper).where(Paper.id.in_(paper_ids)).order_by(Paper.title)
                )
            )
            .scalars()
            .all()
        )
        paper_map = {paper.id: paper for paper in papers}
        blocks = [f"Mission topic: {mission.topic}", f"Objective: {mission.objective}"]
        for section in review_sections:
            blocks.append(
                f"\n[REVIEW title={section.title!r} status={section.status}]\n"
                f"Purpose: {section.purpose}\nDraft: {section.body}\n"
                f"Validated claims: {json.dumps(section.claims_json, ensure_ascii=False)}"
            )
        remaining = 38_000
        for source in sources:
            paper = paper_map.get(source.paper_id)
            if paper is None:
                continue
            header = (
                "\n[EVIDENCE "
                f"paper_id={paper.id} section_id={source.id} seq={source.seq} "
                f"heading={source.heading!r} title={paper.title!r}]\n"
            )
            if remaining <= len(header):
                break
            body = source.body[: max(0, remaining - len(header))]
            blocks.append(header + body)
            remaining -= len(header) + len(body)
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content="\n".join(blocks)),
        ]

    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        del whitelist, citation_sources, usage
        raw = json.loads(output_text)
        payload = UpsertExperimentPlanRequest.model_validate(
            {**raw, "status": "needs_review", "expected_version": None}
        )
        mission, plan, _review_sections, _sources = await self._context(actx)
        await ExperimentPlanService(actx.db)._validate_baselines(mission.id, payload.baselines)
        if plan is None:
            plan = ExperimentPlan(
                project_id=actx.project_id,
                mission_id=mission.id,
                title=payload.title,
                created_by=actx.actor.id,
                updated_by=actx.actor.id,
            )
            actx.db.add(plan)
        else:
            plan.version += 1
        data = payload.model_dump(mode="json", exclude={"expected_version"})
        for name in ("title", "research_gap", "hypothesis", "status"):
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
        plan.generated_by_run_id = actx.run.id
        plan.updated_by = actx.actor.id
        await record_plan_version(actx.db, plan, actx.actor.id, "agent", source_run_id=actx.run.id)
        actx.db.add(
            MissionEvent(
                project_id=actx.project_id,
                mission_id=mission.id,
                event_type="experiment_plan.generated",
                summary=f"Agent 生成结构化实验方案 v{plan.version}",
                step_kind=mission.current_step,
                payload_json={
                    "plan_id": str(plan.id),
                    "version": plan.version,
                    "agent_run_id": str(actx.run.id),
                },
                actor_id=actx.actor.id,
            )
        )
        citations = [
            {
                "paper_id": str(item.source_paper_id),
                "section_id": str(item.evidence_section_id),
                "quote": item.evidence_quote,
            }
            for item in payload.baselines
            if item.evidence_status == "grounded"
        ]
        return (
            {
                "message": f"Experiment plan v{plan.version} generated for human review.",
                "experiment_plan_id": str(plan.id),
                "experiment_plan_version": plan.version,
                "baseline_count": len(plan.baselines_json),
                "matrix_count": len(plan.matrix_json),
            },
            citations,
        )
