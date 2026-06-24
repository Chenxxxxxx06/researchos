"""Critic agent: structured novelty/weakness review of an idea.

Cites only papers in the project's library. Persists a ResearchCritique.
"""

from __future__ import annotations

import json
import uuid

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError
from researchos.research.models import ResearchCritique
from researchos.research.repository import CritiqueRepository, IdeaRepository

from .base import Agent, AgentContext
from .citations import filter_citations

_SYSTEM = (
    "You are a critical reviewer for a top AI venue. Use the library.list tool to "
    "see the project's papers, then critique the given idea. Respond with a JSON "
    "object containing: novelty_summary (string), weaknesses (array of strings), "
    "missing_baselines (array), dataset_risks (array), reproducibility (array), and "
    "citations (array of '<source>:<external_id>' keys from the library only). "
    "Never invent citations."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "novelty_summary": {"type": "string"},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "missing_baselines": {"type": "array", "items": {"type": "string"}},
        "dataset_risks": {"type": "array", "items": {"type": "string"}},
        "reproducibility": {"type": "array", "items": {"type": "string"}},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["novelty_summary"],
}


class CriticAgent(Agent):
    agent_type = AgentType.CRITIC
    allowed_tools = ["library.list"]
    response_schema = _SCHEMA

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        idea_id = actx.context.get("idea_id")
        idea = None
        if idea_id:
            idea = await IdeaRepository(actx.db).get_by_id(actx.project_id, uuid.UUID(str(idea_id)))
        if idea is None:
            raise NotFoundError("Idea not found for critic review.")
        user = (
            f"Idea title: {idea.title}\n"
            f"Description: {idea.description}\n"
            f"Hypothesis: {idea.hypothesis or '(none)'}"
        )
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content=user),
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
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = {}

        candidate_keys = [str(k) for k in parsed.get("citations", [])]
        kept, dropped = filter_citations(candidate_keys, whitelist)
        citations = [citation_sources[k] for k in kept if k in citation_sources]

        idea_id = uuid.UUID(str(actx.context["idea_id"]))
        critique = ResearchCritique(
            project_id=actx.project_id,
            idea_id=idea_id,
            agent_run_id=actx.run.id,
            novelty_summary=str(parsed.get("novelty_summary", "")),
            weaknesses_json=list(parsed.get("weaknesses", [])),
            missing_baselines_json=list(parsed.get("missing_baselines", [])),
            dataset_risks_json=list(parsed.get("dataset_risks", [])),
            reproducibility_json=list(parsed.get("reproducibility", [])),
            citations_json=kept,
        )
        await CritiqueRepository(actx.db).create(critique)

        output_json = {
            "critique_id": str(critique.id),
            "novelty_summary": critique.novelty_summary,
            "weaknesses": critique.weaknesses_json,
            "missing_baselines": critique.missing_baselines_json,
            "dataset_risks": critique.dataset_risks_json,
            "reproducibility": critique.reproducibility_json,
            "citations": kept,
            "dropped_citations": dropped,
        }
        return output_json, citations
