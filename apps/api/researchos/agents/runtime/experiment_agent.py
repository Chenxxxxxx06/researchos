"""Experiment analysis agent.

Computes a deterministic, source-backed summary from a run's metrics (best and
final values) so the analysis never fabricates numbers. The LLM text is a
wrapper; the facts come from the database.
"""

from __future__ import annotations

import uuid

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError

from .base import Agent, AgentContext

_SYSTEM = (
    "You are an experiment analyst. Summarize the run using only the metrics "
    "provided. Do not invent numbers."
)


def _summarize(metrics: list) -> tuple[str, dict]:
    by_name: dict[str, list[tuple[int, float]]] = {}
    for m in metrics:
        by_name.setdefault(m.name, []).append((m.step, m.value))

    final: dict[str, float] = {}
    best: dict[str, float] = {}
    for name, points in by_name.items():
        points.sort(key=lambda p: p[0])
        final[name] = points[-1][1]
        values = [v for _, v in points]
        best[name] = min(values) if "loss" in name.lower() else max(values)

    lines = []
    for name in sorted(by_name):
        lines.append(f"- {name}: final={final[name]:.4f}, best={best[name]:.4f}")
    text = "Experiment run analysis (computed from recorded metrics):\n" + (
        "\n".join(lines) if lines else "No metrics recorded yet."
    )
    return text, {"final": final, "best": best}


class ExperimentAgent(Agent):
    agent_type = AgentType.EXPERIMENT
    allowed_tools: list[str] = []
    response_schema = None

    async def _metrics(self, actx: AgentContext) -> list:
        from researchos.experiments.service import ExperimentService

        run_id = actx.context.get("experiment_run_id")
        if not run_id:
            raise NotFoundError("experiment_run_id is required.")
        return await ExperimentService(actx.db).list_metrics(
            actx.actor, actx.project_id, uuid.UUID(str(run_id))
        )

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        metrics = await self._metrics(actx)
        text, _ = _summarize(metrics)
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content=f"Analyze this run.\n{text}"),
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
        metrics = await self._metrics(actx)
        text, summary = _summarize(metrics)
        return {"message": text, "summary": summary}, []
