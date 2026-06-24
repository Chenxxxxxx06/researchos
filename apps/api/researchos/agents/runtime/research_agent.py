"""Research agent: finds papers and produces a source-backed synthesis."""

from __future__ import annotations

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage

from .base import Agent, AgentContext
from .citations import filter_citations

_SYSTEM = (
    "You are a research assistant for an AI researcher. Use the paper.search tool "
    "to find relevant literature, then synthesize a concise, source-backed answer. "
    "Only cite papers returned by the tools. Never invent citations. If you are "
    "unsure, say so and mark the statement as an assumption."
)


class ResearchAgent(Agent):
    agent_type = AgentType.RESEARCH
    allowed_tools = ["paper.search", "library.list"]
    response_schema = None

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content=actx.message),
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
        # Research cites everything it actually retrieved (all whitelisted papers).
        kept, _dropped = filter_citations(list(whitelist), whitelist)
        citations = [citation_sources[k] for k in kept if k in citation_sources]
        output_json = {"message": output_text, "citations": kept}
        return output_json, citations
