"""LaTeX writing assistant agent (mock).

Produces writing suggestions for the paper workspace. It does not invent
citations and marks anything speculative as an assumption. The mock provider
returns deterministic guidance; a real provider plugs in via config.
"""

from __future__ import annotations

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage

from .base import Agent, AgentContext

_SYSTEM = (
    "You are an academic writing assistant for LaTeX papers. Improve clarity and "
    "academic tone. Do not invent citations; mark speculative claims as assumptions."
)


class LatexAgent(Agent):
    agent_type = AgentType.LATEX
    allowed_tools: list[str] = []
    response_schema = None

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        selection = str(actx.context.get("selection", "")).strip()
        user = actx.message
        if selection:
            user = f"{actx.message}\n\nSelected text:\n{selection}"
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
        return {"message": output_text}, []
