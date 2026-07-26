"""Agent base classes and the per-run context."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.agents.models import AgentRun
from researchos.identity.models import User

from .skills_injection import render_skill_block
from .tools import ToolContext

if TYPE_CHECKING:
    from researchos.skills.service import RuntimeSkill


@dataclass
class AgentContext:
    db: AsyncSession
    actor: User
    project_id: uuid.UUID
    run: AgentRun
    message: str
    context: dict
    tool_ctx: ToolContext
    skills: list[RuntimeSkill] = field(default_factory=list)


class Agent(ABC):
    """Base class for agents. Agents declare prompts, tools, and how to finalize.

    The runtime drives the LLM/tool loop; agents never call the LLM or tools
    directly.
    """

    agent_type: AgentType
    allowed_tools: list[str] = []
    response_schema: dict | None = None
    # Per-agent tool budget override; None falls back to settings.
    max_tool_calls: int | None = None

    @abstractmethod
    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]: ...

    async def build_prompt(self, actx: AgentContext) -> list[LLMMessage]:
        """Skill-augmented prompt: ``build_messages`` plus the active-skills block.

        Concrete so agent subclasses (which override only ``build_messages``)
        get skill injection for free.
        """

        messages = await self.build_messages(actx)
        block = render_skill_block(actx.skills)
        if block:
            if messages and messages[0].role == "system":
                messages[0] = LLMMessage(
                    role="system", content=messages[0].content + "\n\n" + block
                )
            else:
                messages.insert(0, LLMMessage(role="system", content=block))
        return messages

    async def prevalidate(self, actx: AgentContext, output_text: str) -> str | None:
        """Optional self-repair hook: return feedback to re-stream ONCE, or None.

        The runtime appends a non-None return as a user message and runs one
        corrective iteration before finalize (e.g. the coding agent lists edit
        violations so the model can re-anchor).
        """

        return None

    @abstractmethod
    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        """Return ``(output_json, citation_dicts)`` and persist any domain records."""
