# ruff: noqa: E501
"""Specialized agents for the long-running research program.

These roles exchange bounded, typed artifacts through the mission coordinator.
They do not chat with each other or mutate task state directly.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import select

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError, ValidationError
from researchos.experiments.models import ExperimentMetric, ExperimentRun
from researchos.figures.figure_service import FigureService
from researchos.figures.schemas import CreateFigureRequest
from researchos.knowledge.models import ReadingCard
from researchos.knowledge.service import KnowledgeService
from researchos.missions.models import ResearchMission
from researchos.orchestration.models import MissionTask, TaskArtifact
from researchos.research.enums import IdeaStatus
from researchos.research.models import Idea, Paper
from researchos.research.service import IdeaService

from .base import Agent, AgentContext

_DIRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "directions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "rationale": {"type": "string"},
                    "source_paper_ids": {"type": "array", "items": {"type": "string"}},
                    "benchmark_plan": {"type": "array", "items": {"type": "string"}},
                    "ablation_plan": {"type": "array", "items": {"type": "string"}},
                    "pilot_scope": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["title", "hypothesis", "rationale", "source_paper_ids", "score"],
            },
        }
    },
    "required": ["directions"],
}

_BENCHMARK_SCHEMA = {
    "type": "object",
    "properties": {
        "benchmarks": {"type": "array", "items": {"type": "object"}},
        "primary_benchmark": {"type": "string"},
        "primary_metric": {"type": "string"},
        "pilot_matrix": {"type": "array", "items": {"type": "object"}},
        "full_matrix": {"type": "array", "items": {"type": "object"}},
        "ablations": {"type": "array", "items": {"type": "object"}},
        "decision_rules": {"type": "array", "items": {"type": "string"}},
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "benchmarks",
        "primary_benchmark",
        "primary_metric",
        "pilot_matrix",
        "full_matrix",
        "ablations",
        "decision_rules",
        "stop_conditions",
    ],
}

_VIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "revise", "reject"]},
        "confidence": {"type": "number"},
        "blocking_findings": {"type": "array", "items": {"type": "string"}},
        "non_blocking_findings": {"type": "array", "items": {"type": "string"}},
        "evidence_checked": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
    "required": ["verdict", "confidence", "blocking_findings", "next_action"],
}

_LEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": [
                "try_direction",
                "continue_pilot",
                "revise_code",
                "scale_experiments",
                "write",
                "stop",
            ],
        },
        "direction_rank": {"type": ["integer", "null"]},
        "rationale": {"type": "string"},
        "next_task": {"type": "string"},
        "required_approvals": {"type": "array", "items": {"type": "string"}},
        "budget_note": {"type": "string"},
    },
    "required": ["decision", "rationale", "next_task", "required_approvals"],
}

_WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "venue": {"type": "string"},
        "section": {"type": "string"},
        "latex": {"type": "string"},
        "citation_keys": {"type": "array", "items": {"type": "string"}},
        "claim_links": {"type": "array", "items": {"type": "object"}},
        "unresolved_evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "venue",
        "section",
        "latex",
        "citation_keys",
        "claim_links",
        "unresolved_evidence",
    ],
}

_DRAWER_SCHEMA = {
    "type": "object",
    "properties": {
        "mermaid": {"type": "string"},
        "figures": {"type": "array", "items": {"type": "object"}},
        "tables": {"type": "array", "items": {"type": "object"}},
        "captions": {"type": "array", "items": {"type": "string"}},
        "source_run_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["mermaid", "figures", "tables", "captions", "source_run_ids"],
}

_PROGRESS_SCHEMA = {
    "type": "object",
    "properties": {
        "progress_percent": {"type": "number"},
        "active_agents": {"type": "array", "items": {"type": "string"}},
        "completed": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "array", "items": {"type": "string"}},
        "eta_basis": {"type": "string"},
    },
    "required": ["progress_percent", "active_agents", "completed", "blockers", "next_actions"],
}


async def _mission_id(actx: AgentContext) -> uuid.UUID:
    try:
        mission_id = uuid.UUID(str(actx.context["mission_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("This agent requires mission_id.") from exc
    mission = await actx.db.get(ResearchMission, mission_id)
    if mission is None or mission.project_id != actx.project_id:
        raise NotFoundError("Research mission not found for this agent.")
    return mission_id


async def _snapshot(actx: AgentContext) -> dict[str, Any]:
    mission_id = await _mission_id(actx)
    mission = await actx.db.get(ResearchMission, mission_id)
    assert mission is not None
    card_rows = (
        await actx.db.execute(
            select(ReadingCard, Paper)
            .join(Paper, Paper.id == ReadingCard.paper_id)
            .where(ReadingCard.mission_id == mission_id)
            .order_by(Paper.title.asc())
            .limit(50)
        )
    ).all()
    tasks = list(
        (
            await actx.db.execute(
                select(MissionTask)
                .where(MissionTask.mission_id == mission_id)
                .order_by(MissionTask.priority.asc())
            )
        )
        .scalars()
        .all()
    )
    artifacts = list(
        (
            await actx.db.execute(
                select(TaskArtifact)
                .where(TaskArtifact.mission_id == mission_id)
                .order_by(TaskArtifact.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    ideas = list(
        (
            await actx.db.execute(
                select(Idea)
                .where(
                    Idea.project_id == actx.project_id,
                    Idea.metadata_json["mission_id"].astext == str(mission_id),
                )
                .order_by(Idea.novelty_score.desc().nullslast(), Idea.created_at.asc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    runs = list(
        (
            await actx.db.execute(
                select(ExperimentRun)
                .where(
                    ExperimentRun.project_id == actx.project_id,
                    ExperimentRun.config_json["mission_id"].astext == str(mission_id),
                )
                .order_by(ExperimentRun.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    run_ids = [run.id for run in runs]
    metrics = (
        list(
            (
                await actx.db.execute(
                    select(ExperimentMetric)
                    .where(ExperimentMetric.run_id.in_(run_ids))
                    .order_by(ExperimentMetric.run_id, ExperimentMetric.name, ExperimentMetric.step)
                    .limit(1000)
                )
            )
            .scalars()
            .all()
        )
        if run_ids
        else []
    )
    metrics_by_run: dict[str, list[dict]] = {}
    for metric in metrics:
        metrics_by_run.setdefault(str(metric.run_id), []).append(
            {"name": metric.name, "step": metric.step, "value": metric.value}
        )
    return {
        "dependency_artifacts": list(actx.context.get("input_artifacts") or [])[:50],
        "mission": {
            "id": str(mission.id),
            "topic": mission.topic,
            "objective": mission.objective,
            "scope": mission.scope_json,
            "status": mission.status.value,
        },
        "papers": [
            {
                "paper_id": str(paper.id),
                "citation_key": f"{paper.source}:{paper.external_id}",
                "title": paper.title,
                "summary": card.summary,
                "ideas": card.paper_ideas_json,
                "benchmarks": card.benchmarks_json,
                "ablations": card.ablation_findings_json,
                "repositories": card.github_repositories_json,
                "limitations": card.limitations_json,
                "status": card.status,
            }
            for card, paper in card_rows
        ],
        "ideas": [
            {
                "id": str(idea.id),
                "title": idea.title,
                "hypothesis": idea.hypothesis,
                "score": idea.novelty_score,
                "status": idea.status.value,
                "metadata": idea.metadata_json,
            }
            for idea in ideas
        ],
        "tasks": [
            {
                "key": task.task_key,
                "role": task.role,
                "status": task.status,
                "attempt": task.attempt,
                "output": task.output_json,
                "error": task.last_error_json,
            }
            for task in tasks
        ],
        "artifacts": [
            {
                "schema": artifact.schema_name,
                "hash": artifact.content_hash,
                "metadata": artifact.metadata_json,
            }
            for artifact in artifacts
        ],
        "runs": [
            {
                "id": str(run.id),
                "name": run.name,
                "status": run.status.value,
                "git_commit": run.git_commit,
                "config": run.config_json,
                "metrics": metrics_by_run.get(str(run.id), [])[-100:],
            }
            for run in runs
        ],
    }


def _snapshot_message(snapshot: dict[str, Any], instruction: str) -> str:
    return f"{instruction}\n\nRESEARCH PROGRAM SNAPSHOT:\n{json.dumps(snapshot, ensure_ascii=False)[:48_000]}"


class IdeaExplorerAgent(Agent):
    agent_type = AgentType.IDEA_EXPLORER
    allowed_tools: list[str] = []
    response_schema = _DIRECTION_SCHEMA

    def __init__(self) -> None:
        self.allowed_paper_ids: set[str] = set()

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        mission_id = await _mission_id(actx)
        synthesis = await KnowledgeService(actx.db).research_synthesis(
            actx.actor, actx.project_id, mission_id
        )
        self.allowed_paper_ids = {
            str(paper_id) for item in synthesis.directions for paper_id in item.source_paper_ids
        }
        payload = synthesis.model_dump(mode="json")
        system = (
            "You are the Idea Explorer. Return at most ten falsifiable directions ranked by "
            "evidence strength, benchmark value, ablation information, code availability, cost, "
            "and novelty risk. Use only supplied paper ids. Each direction must include a small "
            "pilot scope before full experiments. Never claim an inferred idea is a paper result."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(
                role="user",
                content=f"Refine and rank this deterministic evidence slate:\n{json.dumps(payload, ensure_ascii=False)}",
            ),
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
        mission_id = await _mission_id(actx)
        parsed = json.loads(output_text)
        created: list[str] = []
        directions: list[dict] = []
        limit = min(10, max(1, int(actx.context.get("max_directions") or 10)))
        for rank, raw in enumerate(list(parsed.get("directions") or [])[:limit], start=1):
            if not isinstance(raw, dict):
                continue
            source_ids = [
                value
                for value in (str(item) for item in raw.get("source_paper_ids") or [])
                if value in self.allowed_paper_ids
            ]
            title = str(raw.get("title") or "").strip()[:300]
            hypothesis = str(raw.get("hypothesis") or "").strip()
            if not title or not hypothesis:
                continue
            score = max(0.0, min(1.0, float(raw.get("score") or 0.0)))
            idea = Idea(
                project_id=actx.project_id,
                title=title,
                description=str(raw.get("rationale") or "").strip(),
                hypothesis=hypothesis,
                novelty_score=score,
                metadata_json={
                    "source": "idea-explorer/v1",
                    "mission_id": str(mission_id),
                    "rank": rank,
                    "source_paper_ids": source_ids,
                    "benchmark_plan": list(raw.get("benchmark_plan") or [])[:20],
                    "ablation_plan": list(raw.get("ablation_plan") or [])[:20],
                    "pilot_scope": str(raw.get("pilot_scope") or "small-batch pilot"),
                    "generated_by_run_id": str(actx.run.id),
                },
                created_by=actx.actor.id,
            )
            actx.db.add(idea)
            await actx.db.flush()
            created.append(str(idea.id))
            directions.append(
                {**raw, "idea_id": str(idea.id), "rank": rank, "source_paper_ids": source_ids}
            )
        if not directions:
            raise ValidationError("Idea Explorer produced no valid evidence-linked direction.")
        return {
            "message": f"Ranked {len(directions)} directions.",
            "idea_ids": created,
            "directions": directions,
        }, []


class BenchmarkAgent(Agent):
    agent_type = AgentType.BENCHMARK
    allowed_tools: list[str] = []
    response_schema = _BENCHMARK_SCHEMA

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        mission_id = await _mission_id(actx)
        synthesis = await KnowledgeService(actx.db).research_synthesis(
            actx.actor, actx.project_id, mission_id
        )
        system = (
            "You are the Benchmark Planner. Rank only benchmarks found in the evidence slate. "
            "Prefer multi-paper support, explicit metrics/splits, code availability, and ablation "
            "utility. Design a cheap pilot matrix first and a full matrix only after a Viewer pass. "
            "Include baselines, seeds, controls, decision rules, and stop conditions. Never invent "
            "a dataset, metric, license, split, or result."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(
                role="user",
                content=f"{actx.message}\n\nEVIDENCE SLATE:\n{json.dumps(synthesis.model_dump(mode='json'), ensure_ascii=False)}",
            ),
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
        del actx, whitelist, citation_sources, usage
        return json.loads(output_text), []


class ViewerAgent(Agent):
    agent_type = AgentType.VIEWER
    allowed_tools: list[str] = []
    response_schema = _VIEWER_SCHEMA

    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        snapshot = await _snapshot(actx)
        self.snapshot = snapshot
        system = (
            "You are an independent Viewer/Reviewer. Check code/run/artifact evidence, pilot scope, "
            "metric integrity, leakage, reproducibility, and whether a claimed completion has a real "
            "receipt. Pass only when blockers are empty. You advise; you never mutate artifacts."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=_snapshot_message(snapshot, actx.message)),
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
        del actx, whitelist, citation_sources, usage
        parsed = json.loads(output_text)
        recorded_metric_names = {
            str(metric.get("name"))
            for run in self.snapshot.get("runs", [])
            for metric in run.get("metrics", [])
            if isinstance(metric, dict)
        }
        scientific_metrics = recorded_metric_names - {"command_success", "test_pass_rate"}
        if not scientific_metrics and any(
            str(run.get("config", {}).get("scale")) in {"pilot", "full"}
            for run in self.snapshot.get("runs", [])
        ):
            parsed["verdict"] = "revise"
            blockers = list(parsed.get("blocking_findings") or [])
            blockers.append("No declared scientific primary metric is recorded for the pilot.")
            parsed["blocking_findings"] = list(dict.fromkeys(blockers))
            parsed["next_action"] = (
                "Instrument the pilot with RESEARCHOS_METRIC JSON lines for the primary metric."
            )
        parsed["confidence"] = max(0.0, min(1.0, float(parsed.get("confidence") or 0.0)))
        return parsed, []


class LeaderAgent(Agent):
    agent_type = AgentType.LEADER
    allowed_tools: list[str] = []
    response_schema = _LEADER_SCHEMA

    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        snapshot = await _snapshot(actx)
        self.snapshot = snapshot
        system = (
            "You are the Research Lead. Choose exactly one next action from the schema. Work through "
            "ranked directions one at a time. Start with a bounded pilot; scale only after a Viewer "
            "pass and recorded metrics. External APIs, paid compute, new datasets, and secrets must "
            "appear in required_approvals. Stop on repeated no-progress or integrity failures."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=_snapshot_message(snapshot, actx.message)),
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
        parsed = json.loads(output_text)
        viewer_reports = [
            artifact.get("metadata", {})
            for artifact in self.snapshot.get("artifacts", [])
            if str(artifact.get("schema")) == "agent-run/viewer"
        ]
        if viewer_reports and viewer_reports[0].get("verdict") != "pass":
            parsed["decision"] = "revise_code"
            parsed["next_task"] = str(
                viewer_reports[0].get("next_action")
                or "Resolve the latest Viewer blockers before scaling."
            )
            parsed["required_approvals"] = list(
                dict.fromkeys(list(parsed.get("required_approvals") or []))
            )
        if str(actx.context.get("task_key") or "") == "direction":
            rank = int(parsed.get("direction_rank") or 1)
            candidates = list(
                (
                    await actx.db.execute(
                        select(Idea)
                        .where(
                            Idea.project_id == actx.project_id,
                            Idea.metadata_json["mission_id"].astext
                            == str(actx.context.get("mission_id")),
                        )
                        .order_by(Idea.novelty_score.desc().nullslast(), Idea.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            if candidates:
                selected = candidates[min(max(rank - 1, 0), len(candidates) - 1)]
                await IdeaService(actx.db).update(
                    actx.actor,
                    actx.project_id,
                    selected.id,
                    title=None,
                    description=None,
                    hypothesis=None,
                    status=IdeaStatus.ACTIVE,
                )
                parsed["selected_idea_id"] = str(selected.id)
                parsed["selected_idea_title"] = selected.title
        return parsed, []


class WriterAgent(Agent):
    agent_type = AgentType.WRITER
    allowed_tools: list[str] = []
    response_schema = _WRITER_SCHEMA

    def __init__(self) -> None:
        self.allowed_citations: set[str] = set()
        self.allowed_numbers: set[str] = set()

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        snapshot = await _snapshot(actx)
        self.allowed_citations = {str(item["citation_key"]) for item in snapshot["papers"]}
        self.allowed_numbers = {
            representation
            for run in snapshot["runs"]
            for metric in run["metrics"]
            for representation in _number_representations(float(metric["value"]))
        }
        venue = str(actx.context.get("venue") or "generic").strip()
        section = str(actx.context.get("section") or "methods").strip()
        system = (
            "You are the evidence-bound Writer. Draft only the requested manuscript section in "
            "LaTeX. Every numeric result must match a recorded run metric; every citation key must "
            "come from the supplied library. Mark unsupported statements in unresolved_evidence. "
            "Adapt structure and density to the requested venue without inventing policy."
        )
        instruction = f"Venue: {venue}\nSection: {section}\n{actx.message}"
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=_snapshot_message(snapshot, instruction)),
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
        parsed = json.loads(output_text)
        latex = str(parsed.get("latex") or "")
        embedded = {
            key.strip()
            for group in re.findall(r"\\cite(?:[a-zA-Z*]*)?\{([^}]+)\}", latex)
            for key in group.split(",")
            if key.strip()
        }
        requested = {str(value) for value in parsed.get("citation_keys") or []} | embedded
        unknown_citations = sorted(requested - self.allowed_citations)
        if unknown_citations:
            raise ValidationError(
                "Writer output contains citation keys outside the mission allowlist: "
                + ", ".join(unknown_citations)
            )
        numbers = set(
            re.findall(
                r"(?<![A-Za-z\\])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?",
                latex,
                re.I,
            )
        )
        unresolved_numbers = sorted(
            value
            for value in numbers
            if value not in self.allowed_numbers and value not in {"0", "1"}
        )
        if unresolved_numbers:
            raise ValidationError(
                "Writer output contains numbers without recorded metric anchors: "
                + ", ".join(unresolved_numbers)
            )
        parsed["citation_keys"] = sorted(requested)
        parsed["dropped_citation_keys"] = []
        parsed["validated_numeric_tokens"] = sorted(numbers)

        from researchos.documents.models import LatexProject
        from researchos.documents.service import DocumentService
        from researchos.documents.venue_templates import VENUE_TEMPLATES

        latex_project = await actx.db.scalar(
            select(LatexProject)
            .where(LatexProject.project_id == actx.project_id)
            .order_by(LatexProject.created_at.asc())
            .limit(1)
        )
        venue = str(parsed.get("venue") or actx.context.get("venue") or "generic").lower()
        if latex_project is None:
            latex_project = await DocumentService(actx.db).create_latex_project(
                actx.actor,
                actx.project_id,
                name=f"{venue.upper()} Research Paper",
                template_id=venue if venue in VENUE_TEMPLATES else "article",
            )
        section_name = (
            re.sub(
                r"[^a-z0-9_-]+",
                "-",
                str(parsed.get("section") or actx.context.get("section") or "draft").lower(),
            ).strip("-")
            or "draft"
        )
        path = f"sections/autopilot-{section_name}.tex"
        current_file = await DocumentService(actx.db).files.get_by_path(latex_project.id, path)
        written = await DocumentService(actx.db).write_file_versioned(
            actx.actor,
            latex_project.id,
            path=path,
            content=latex,
            expected_version=current_file.version if current_file is not None else None,
        )
        parsed["document_file_id"] = str(written.id)
        parsed["document_path"] = path
        parsed["document_version"] = written.version
        return parsed, []


class DrawerAgent(Agent):
    agent_type = AgentType.DRAWER
    allowed_tools: list[str] = []
    response_schema = _DRAWER_SCHEMA

    def __init__(self) -> None:
        self.allowed_numbers: set[str] = set()
        self.allowed_run_ids: set[str] = set()

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        snapshot = await _snapshot(actx)
        self.allowed_run_ids = {str(run["id"]) for run in snapshot["runs"]}
        self.allowed_numbers = {
            representation
            for run in snapshot["runs"]
            for metric in run["metrics"]
            for representation in _number_representations(float(metric["value"]))
        }
        system = (
            "You are the Figure and Table Agent. Return a left-to-right Mermaid method flow, "
            "publication-quality FigureSpec objects using only recorded metrics, LaTeX tables with "
            "values copied from runs, and concise captions. Use a restrained colorblind-safe style. "
            "Never fabricate a series, number, run id, benchmark, or citation. Mermaid nodes need "
            "semantic ids and every arrow must represent a real dependency."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=_snapshot_message(snapshot, actx.message)),
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
        parsed = json.loads(output_text)
        mermaid = str(parsed.get("mermaid") or "").strip()
        parsed["mermaid_valid"] = _valid_mermaid(mermaid)
        created: list[dict] = []
        diagnostics: list[str] = []
        for raw in list(parsed.get("figures") or [])[:8]:
            if not isinstance(raw, dict):
                continue
            try:
                request = CreateFigureRequest.model_validate(raw)
                for series in request.spec.series:
                    source = series.source
                    if source.kind != "run_metric":
                        raise ValidationError(
                            "Autonomous Drawer figures require run_metric sources; "
                            "inline values are forbidden."
                        )
                    if source.run_id is not None and str(source.run_id) not in self.allowed_run_ids:
                        raise ValidationError("Drawer referenced a run outside the mission.")
                figure = await FigureService(actx.db).create_figure(
                    actx.actor, actx.project_id, request
                )
                rendered = await FigureService(actx.db).render(
                    actx.actor, actx.project_id, figure.id, mode="sync"
                )
                created.append(
                    {
                        "figure_id": str(figure.id),
                        "name": figure.name,
                        "status": rendered.status.value,
                        "assets": [asset.model_dump(mode="json") for asset in rendered.assets],
                    }
                )
            except Exception as exc:  # noqa: BLE001 - keep other valid figures
                diagnostics.append(str(exc)[:500])
        table_numbers = {
            value
            for table in list(parsed.get("tables") or [])
            for value in re.findall(
                r"(?<![A-Za-z\\])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?",
                json.dumps(table, ensure_ascii=False),
                re.I,
            )
        }
        unresolved_table_numbers = sorted(
            value
            for value in table_numbers
            if value not in self.allowed_numbers and value not in {"0", "1"}
        )
        if unresolved_table_numbers:
            raise ValidationError(
                "Drawer tables contain values without recorded metric anchors: "
                + ", ".join(unresolved_table_numbers)
            )
        parsed["created_figures"] = created
        parsed["figure_diagnostics"] = diagnostics
        parsed["source_run_ids"] = sorted(
            {
                str(series.source.run_id)
                for raw in list(parsed.get("figures") or [])
                if isinstance(raw, dict)
                for series in CreateFigureRequest.model_validate(raw).spec.series
                if series.source.kind == "run_metric" and series.source.run_id is not None
            }
        )
        if not parsed["mermaid_valid"]:
            raise ValidationError("Mermaid failed deterministic safety/syntax preflight.")

        from researchos.documents.models import LatexProject
        from researchos.documents.service import DocumentService

        latex_project = await actx.db.scalar(
            select(LatexProject)
            .where(LatexProject.project_id == actx.project_id)
            .order_by(LatexProject.created_at.asc())
            .limit(1)
        )
        if latex_project is None:
            latex_project = await DocumentService(actx.db).create_latex_project(
                actx.actor, actx.project_id, name="Research Paper", template_id="article"
            )
        document_service = DocumentService(actx.db)
        mermaid_file = await document_service.files.get_by_path(
            latex_project.id, "figures/autopilot-method.mmd"
        )
        await document_service.write_file_versioned(
            actx.actor,
            latex_project.id,
            path="figures/autopilot-method.mmd",
            content=mermaid + "\n",
            expected_version=mermaid_file.version if mermaid_file is not None else None,
        )
        markdown = (
            "# Method flow\n\nEvidence-bound method and experiment flow.\n\n"
            f"```mermaid\n{mermaid}\n```\n"
        )
        markdown_file = await document_service.files.get_by_path(
            latex_project.id, "figures/autopilot-method.md"
        )
        await document_service.write_file_versioned(
            actx.actor,
            latex_project.id,
            path="figures/autopilot-method.md",
            content=markdown,
            expected_version=markdown_file.version if markdown_file is not None else None,
        )
        table_latex = "\n\n".join(
            str(table.get("latex") or "")
            for table in list(parsed.get("tables") or [])
            if isinstance(table, dict) and str(table.get("latex") or "").strip()
        )
        if table_latex:
            table_file = await document_service.files.get_by_path(
                latex_project.id, "tables/autopilot-results.tex"
            )
            await document_service.write_file_versioned(
                actx.actor,
                latex_project.id,
                path="tables/autopilot-results.tex",
                content=table_latex + "\n",
                expected_version=table_file.version if table_file is not None else None,
            )
        parsed["document_paths"] = [
            "figures/autopilot-method.mmd",
            "figures/autopilot-method.md",
            *(["tables/autopilot-results.tex"] if table_latex else []),
        ]
        return parsed, []


class ProgressAgent(Agent):
    agent_type = AgentType.PROGRESS
    allowed_tools: list[str] = []
    response_schema = _PROGRESS_SCHEMA

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        snapshot = await _snapshot(actx)
        task_count = len(snapshot["tasks"])
        completed = sum(item["status"] == "completed" for item in snapshot["tasks"])
        snapshot["deterministic_progress_percent"] = (
            round(100 * completed / task_count, 2) if task_count else 0
        )
        system = (
            "You are the Progress Controller. Report the deterministic completion percentage exactly. "
            "List active agents, blockers, failed receipts, and the smallest next actions. ETA must "
            "state its evidence basis and must not be invented. You monitor; you do not approve work."
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=_snapshot_message(snapshot, actx.message)),
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
        del actx, whitelist, citation_sources, usage
        parsed = json.loads(output_text)
        parsed["progress_percent"] = max(
            0.0, min(100.0, float(parsed.get("progress_percent") or 0.0))
        )
        return parsed, []


def _number_representations(value: float) -> set[str]:
    return {
        str(value),
        f"{value:g}",
        f"{value:.2f}",
        f"{value:.3f}",
        f"{value:.4f}",
    }


def _valid_mermaid(value: str) -> bool:
    if not value or not value.lstrip().startswith(("flowchart ", "graph ")):
        return False
    lowered = value.lower()
    if any(token in lowered for token in ("<script", "javascript:", "click ", "%%{init")):
        return False
    return all(
        value.count(left) == value.count(right)
        for left, right in (("[", "]"), ("{", "}"), ("(", ")"))
    )
