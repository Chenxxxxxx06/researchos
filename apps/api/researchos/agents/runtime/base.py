"""Agent base classes and the per-run context."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.agents.models import AgentRun
from researchos.identity.models import User

from .tools import ToolContext


@dataclass
class AgentContext:
    db: AsyncSession
    actor: User
    project_id: uuid.UUID
    run: AgentRun
    message: str
    context: dict
    tool_ctx: ToolContext


class Agent(ABC):
    """Base class for agents. Agents declare prompts, tools, and how to finalize.

    The runtime drives the LLM/tool loop; agents never call the LLM or tools
    directly.
    """

    agent_type: AgentType
    allowed_tools: list[str] = []
    response_schema: dict | None = None

    @abstractmethod
    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]: ...

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
