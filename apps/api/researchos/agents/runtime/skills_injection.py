"""Skill runtime injection: prompt fragments and tool grants.

Enabled project skills change agent behavior in two auditable ways: their
``prompt_template`` is appended to the system prompt (as inert text — never
evaluated), and their declared ``tool_permissions`` may widen the agent's tool
set (bounded by the platform allowlist and the live tool registry).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentType
from researchos.skills.enums import SkillModule
from researchos.skills.service import RuntimeSkill, SkillService

logger = structlog.get_logger(__name__)

_MODULE_BY_AGENT: dict[AgentType, SkillModule] = {
    AgentType.RESEARCH: SkillModule.RESEARCH,
    AgentType.CRITIC: SkillModule.RESEARCH,
    AgentType.CODING: SkillModule.IDE,
    AgentType.EXPERIMENT: SkillModule.EXPERIMENTS,
    AgentType.LATEX: SkillModule.PAPER,
}


async def load_skills(
    db: AsyncSession,
    project_id: uuid.UUID,
    agent_type: AgentType,
    *,
    requested_slugs: list[str] | None = None,
) -> list[RuntimeSkill]:
    module = _MODULE_BY_AGENT.get(agent_type)
    if module is None:
        return []
    return await SkillService(db).list_enabled_for_runtime(
        project_id, module, requested_slugs=requested_slugs
    )


def _substitute(template: str, settings: dict) -> str:
    """Replace ``{{key}}`` placeholders from settings via plain str.replace.

    Templates are inert text: values are coerced with ``str()``, unknown
    placeholders are left as-is, and nothing is ever evaluated or formatted.
    """

    out = template
    for key, value in settings.items():
        out = out.replace("{{" + str(key) + "}}", str(value))
    return out


def render_skill_block(skills: list[RuntimeSkill], *, char_budget: int = 8000) -> str:
    """Deterministic prompt block for the active skills ('' when none)."""

    if not skills:
        return ""
    block = "## Active skills"
    dropped: list[str] = []
    truncated = False
    for skill in skills:
        if truncated:
            dropped.append(skill.slug)
            continue
        lines = [f"### {skill.name} v{skill.version}"]
        template = _substitute(skill.prompt_template, skill.settings)
        if template:
            lines.append(template)
        if skill.workflow:
            steps = "; ".join(
                f"{i}) {step}" for i, step in enumerate(skill.workflow, start=1)
            )
            lines.append(f"Suggested workflow: {steps}")
        fragment = "\n" + "\n".join(lines)
        if len(block) + len(fragment) > char_budget:
            remaining = max(0, char_budget - len(block))
            block += fragment[:remaining] + "\n[truncated]"
            truncated = True
            continue
        block += fragment
    if dropped:
        logger.warning("skill_block_truncated", dropped_slugs=dropped)
    return block


def skill_tool_grants(skills: list[RuntimeSkill]) -> dict[str, str]:
    """Map each skill-granted tool name to the FIRST granting skill slug."""

    grants: dict[str, str] = {}
    for skill in skills:
        for tool_name in skill.tool_permissions:
            grants.setdefault(tool_name, skill.slug)
    return grants
