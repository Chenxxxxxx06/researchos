"""Deterministic citation organizer wrapped in a durable AgentRun."""

from __future__ import annotations

import uuid

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.citations.models import MissionCitationAudit
from researchos.citations.service import build_citation_audit, mission_papers
from researchos.common.errors import NotFoundError, ValidationError
from researchos.missions.models import MissionEvent, ResearchMission

from .base import Agent, AgentContext


class CitationOrganizerAgent(Agent):
    agent_type = AgentType.CITATION_ORGANIZER
    allowed_tools: list[str] = []

    async def _mission(self, actx: AgentContext) -> ResearchMission:
        try:
            mission_id = uuid.UUID(str(actx.context["mission_id"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError("Citation organizer runs require mission_id.") from exc
        mission = await actx.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != actx.project_id:
            raise NotFoundError("Research mission not found for citation organization.")
        return mission

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        mission = await self._mission(actx)
        papers = await mission_papers(actx.db, mission.id)
        if not papers:
            raise ValidationError("Include papers before running a citation audit.")
        return [
            LLMMessage(
                role="system",
                content=(
                    "A deterministic organizer will audit the supplied mission paper metadata. "
                    "Do not invent or modify bibliographic fields. Acknowledge the audit briefly."
                ),
            ),
            LLMMessage(
                role="user",
                content="\n".join(
                    f"{paper.id} | {paper.title} | DOI={paper.doi or '-'} | "
                    f"arXiv={paper.arxiv_id or '-'}"
                    for paper in papers
                ),
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
        del output_text, whitelist, citation_sources, usage
        mission = await self._mission(actx)
        papers = await mission_papers(actx.db, mission.id)
        items, duplicates, missing_count, bibtex = build_citation_audit(papers)
        audit = MissionCitationAudit(
            project_id=actx.project_id,
            mission_id=mission.id,
            agent_run_id=actx.run.id,
            items_json=items,
            duplicate_groups_json=duplicates,
            missing_field_count=missing_count,
            bibtex_text=bibtex,
            created_by=actx.actor.id,
        )
        actx.db.add(audit)
        await actx.db.flush()
        actx.db.add(
            MissionEvent(
                project_id=actx.project_id,
                mission_id=mission.id,
                event_type="citations.audited",
                summary=(
                    f"引用整理完成：{len(items)} 条，{missing_count} 个缺失字段，"
                    f"{len(duplicates)} 组疑似重复"
                ),
                step_kind=mission.current_step,
                payload_json={
                    "citation_audit_id": str(audit.id),
                    "agent_run_id": str(actx.run.id),
                    "paper_count": len(items),
                    "missing_field_count": missing_count,
                    "duplicate_group_count": len(duplicates),
                },
                actor_id=actx.actor.id,
            )
        )
        citations = [
            {
                "paper_id": item["paper_id"],
                "title": item["title"],
                "url": item["url"],
                "doi": item["doi"],
                "arxiv_id": item["arxiv_id"],
            }
            for item in items
        ]
        return (
            {
                "message": (
                    f"Citation audit completed for {len(items)} papers; "
                    f"{missing_count} missing fields need review."
                ),
                "citation_audit_id": str(audit.id),
                "paper_count": len(items),
                "missing_field_count": missing_count,
                "duplicate_group_count": len(duplicates),
            },
            citations,
        )
