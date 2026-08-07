"""Evidence-bound literature-review section agent."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.knowledge.models import MissionPaper, ReadingCard
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.research.models import Paper, PaperSection
from researchos.reviews.models import ReviewDocument, ReviewSection
from researchos.reviews.service import ReviewService

from .base import Agent, AgentContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "body": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "paper_id": {"type": "string"},
                    "section_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "inference": {"type": "boolean"},
                },
                "required": ["text", "paper_id", "section_id", "quote"],
            },
        },
    },
    "required": ["body", "claims"],
}

_SYSTEM = """You draft exactly one section of an academic literature review.
Use only the supplied evidence and reading cards. Synthesize across papers instead of listing them.
Every factual claim must include its paper UUID, exact section UUID, and a short verbatim quote from
that section. Mark interpretations with inference=true. If evidence is insufficient, state the gap
explicitly instead of inventing support. Return only the requested JSON object."""


class ReviewSectionAgent(Agent):
    agent_type = AgentType.REVIEW_SECTION
    allowed_tools: list[str] = []
    response_schema = _SCHEMA

    async def _context(
        self, actx: AgentContext
    ) -> tuple[ResearchMission, ReviewDocument, ReviewSection, list[Paper], list[PaperSection]]:
        try:
            mission_id = uuid.UUID(str(actx.context["mission_id"]))
            section_id = uuid.UUID(str(actx.context["section_id"]))
            expected_version = int(actx.context["expected_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                "Review-section runs require mission_id, section_id, and expected_version."
            ) from exc
        mission = await actx.db.get(ResearchMission, mission_id)
        section = await actx.db.get(ReviewSection, section_id)
        if mission is None or mission.project_id != actx.project_id:
            raise NotFoundError("Research mission not found for review generation.")
        if section is None or section.mission_id != mission.id:
            raise NotFoundError("Review section not found for review generation.")
        if section.version != expected_version:
            raise ConflictError(
                "Review section changed after generation was requested.",
                code="review_section_version_conflict",
            )
        review = await actx.db.get(ReviewDocument, section.review_id)
        if review is None:
            raise NotFoundError("Review document not found.")
        cited_ids = []
        for raw_id in section.citations_json:
            try:
                cited_ids.append(uuid.UUID(str(raw_id)))
            except ValueError:
                continue
        if not cited_ids:
            raise ValidationError("Review section has no selected source papers.")
        allowed_ids = set(
            (
                await actx.db.execute(
                    select(MissionPaper.paper_id).where(
                        MissionPaper.mission_id == mission.id,
                        MissionPaper.paper_id.in_(cited_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        papers = list(
            (
                await actx.db.execute(
                    select(Paper)
                    .where(Paper.project_id == actx.project_id, Paper.id.in_(allowed_ids))
                    .order_by(Paper.title)
                )
            )
            .scalars()
            .all()
        )
        sections = list(
            (
                await actx.db.execute(
                    select(PaperSection)
                    .where(PaperSection.paper_id.in_(allowed_ids))
                    .order_by(PaperSection.paper_id, PaperSection.seq)
                )
            )
            .scalars()
            .all()
        )
        if not sections:
            raise ValidationError("Selected papers have no parsed sections for grounded drafting.")
        return mission, review, section, papers, sections

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        mission, _review, section, papers, sections = await self._context(actx)
        paper_map = {paper.id: paper for paper in papers}
        cards = list(
            (
                await actx.db.execute(
                    select(ReadingCard).where(
                        ReadingCard.mission_id == mission.id,
                        ReadingCard.paper_id.in_(list(paper_map)),
                    )
                )
            )
            .scalars()
            .all()
        )
        blocks = [
            f"Mission topic: {mission.topic}",
            f"Section title: {section.title}",
            f"Section purpose: {section.purpose}",
        ]
        for card in cards:
            blocks.append(
                "\n[READING CARD "
                f"paper_id={card.paper_id}]\nSummary: {card.summary}\n"
                f"Research question: {card.research_question}"
            )
        remaining = 42_000
        for source in sections:
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
        parsed = json.loads(output_text)
        mission, review, section, papers, sources = await self._context(actx)
        paper_map = {str(paper.id): paper for paper in papers}
        source_map = {str(source.id): source for source in sources}
        claims: list[dict] = []
        grounded_paper_ids: list[str] = []
        grounded = 0
        for raw in list(parsed.get("claims") or [])[:500]:
            if not isinstance(raw, dict):
                continue
            paper_id = str(raw.get("paper_id") or "")
            section_id = str(raw.get("section_id") or "")
            quote = str(raw.get("quote") or "").strip()
            source = source_map.get(section_id)
            evidence_ok = (
                paper_id in paper_map
                and source is not None
                and str(source.paper_id) == paper_id
                and bool(quote)
                and quote in source.body
            )
            if evidence_ok:
                grounded += 1
                if paper_id not in grounded_paper_ids:
                    grounded_paper_ids.append(paper_id)
            claims.append(
                {
                    "text": str(raw.get("text") or "").strip(),
                    "paper_id": paper_id if evidence_ok else None,
                    "paper_title": paper_map[paper_id].title if evidence_ok else None,
                    "section_id": section_id if evidence_ok else None,
                    "section_seq": source.seq if evidence_ok and source is not None else None,
                    "heading": source.heading if evidence_ok and source is not None else None,
                    "quote": quote if evidence_ok else "",
                    "inference": bool(raw.get("inference", False)),
                    "evidence_status": "grounded" if evidence_ok else "needs_evidence",
                }
            )
        section.body = str(parsed.get("body") or "").strip()
        section.claims_json = claims
        section.citations_json = grounded_paper_ids
        section.status = "needs_review"
        section.version += 1
        section.generated_by_run_id = actx.run.id
        section.updated_by = actx.actor.id
        review.version += 1
        review.status = "draft"
        review.updated_by = actx.actor.id
        all_sections = await ReviewService(actx.db)._sections(review.id)
        await ReviewService(actx.db)._snapshot(
            review,
            all_sections,
            actx.actor.id,
            "agent",
            source_run_id=actx.run.id,
        )
        actx.db.add(
            MissionEvent(
                project_id=actx.project_id,
                mission_id=mission.id,
                event_type="review.section.generated",
                summary=f"Agent 生成综述章节《{section.title}》v{section.version}",
                step_kind=mission.current_step,
                payload_json={
                    "review_id": str(review.id),
                    "section_id": str(section.id),
                    "agent_run_id": str(actx.run.id),
                    "grounded_claims": grounded,
                    "claim_count": len(claims),
                },
                actor_id=actx.actor.id,
            )
        )
        citations = [
            {
                "paper_id": paper_id,
                "title": paper_map[paper_id].title,
                "source": paper_map[paper_id].source,
                "external_id": paper_map[paper_id].external_id,
                "url": paper_map[paper_id].url,
            }
            for paper_id in grounded_paper_ids
        ]
        return (
            {
                "message": f"Review section v{section.version} generated for human review.",
                "review_id": str(review.id),
                "section_id": str(section.id),
                "section_version": section.version,
                "grounded_claims": grounded,
                "claim_count": len(claims),
            },
            citations,
        )
