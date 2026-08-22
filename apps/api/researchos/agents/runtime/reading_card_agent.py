"""Structured, section-grounded reading-card agent."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError, ValidationError
from researchos.knowledge.indexing import index_reading_card_tuples
from researchos.knowledge.models import MissionPaper, ReadingCard
from researchos.knowledge.service import record_card_version
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.research.models import Paper, PaperSection

from .base import Agent, AgentContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "research_question": {"type": "string"},
        "method_flow": {"type": "array", "items": {"type": "string"}},
        "experimental_setup": {"type": "array", "items": {"type": "string"}},
        "key_results": {"type": "array", "items": {"type": "string"}},
        "conclusions": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "reproducibility": {"type": "array", "items": {"type": "string"}},
        "github_repositories": {"type": "array", "items": {"type": "object"}},
        "paper_ideas": {"type": "array", "items": {"type": "object"}},
        "benchmarks": {"type": "array", "items": {"type": "object"}},
        "ablation_findings": {"type": "array", "items": {"type": "object"}},
        "knowledge_tuples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "head": {"type": "string"},
                    "relation": {"type": "string"},
                    "tail": {"type": "string"},
                    "section_id": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                    "inference": {"type": "boolean"},
                },
                "required": ["kind", "head", "relation", "tail"],
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "section_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "inference": {"type": "boolean"},
                },
                "required": ["text", "section_id", "quote"],
            },
        },
    },
    "required": [
        "summary",
        "research_question",
        "method_flow",
        "experimental_setup",
        "key_results",
        "conclusions",
        "strengths",
        "limitations",
        "reproducibility",
        "github_repositories",
        "paper_ideas",
        "benchmarks",
        "ablation_findings",
        "knowledge_tuples",
        "claims",
    ],
}

_SYSTEM = """You create a structured reading card from user-selected paper sections.
Use only the supplied text. Do not add external facts. Every claim must carry the exact section UUID
and a short verbatim quote copied from that section. Mark interpretations with inference=true.
Extract experimental setup, key results, conclusions, reported GitHub/code URLs,
reusable paper ideas, benchmarks, and ablation findings separately. For every repository,
idea, benchmark, ablation, and knowledge tuple, include section_id and an exact supporting
quote when it is reported; mark derived ideas with inference=true. Never guess a repository
URL, benchmark split, score, or ablation effect. Build compact tuples with kind in
{summary,result,code,idea,benchmark,ablation,limitation}, plus head, relation, and tail.
If a detail is absent from the selected sections, say it is not reported.
Return only the requested JSON object."""


class ReadingCardAgent(Agent):
    agent_type = AgentType.READING_CARD
    allowed_tools: list[str] = []
    response_schema = _SCHEMA

    async def _context(
        self, actx: AgentContext
    ) -> tuple[ResearchMission, Paper, list[PaperSection]]:
        try:
            mission_id = uuid.UUID(str(actx.context["mission_id"]))
            paper_id = uuid.UUID(str(actx.context["paper_id"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError("Reading-card runs require mission_id and paper_id.") from exc
        mission = await actx.db.get(ResearchMission, mission_id)
        paper = await actx.db.get(Paper, paper_id)
        if mission is None or mission.project_id != actx.project_id:
            raise NotFoundError("Research mission not found for reading-card generation.")
        if paper is None or paper.project_id != actx.project_id:
            raise NotFoundError("Paper not found for reading-card generation.")
        linked = await actx.db.scalar(
            select(MissionPaper.id).where(
                MissionPaper.mission_id == mission.id,
                MissionPaper.paper_id == paper.id,
            )
        )
        if linked is None:
            raise ValidationError("Paper is not included in this research mission.")
        sections = list(
            (
                await actx.db.execute(
                    select(PaperSection)
                    .where(PaperSection.paper_id == paper.id)
                    .order_by(PaperSection.seq.asc())
                )
            )
            .scalars()
            .all()
        )
        if not sections:
            raise ValidationError("Paper has no parsed sections to ground a reading card.")
        requested = set(actx.context.get("section_kinds") or [])
        if requested:
            sections = [section for section in sections if section.kind.value in requested]
            if not sections:
                raise ValidationError(
                    "The paper has no parsed sections matching the selected reading focus."
                )
        return mission, paper, sections

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        _mission, paper, sections = await self._context(actx)
        key = f"{paper.source}:{paper.external_id}"
        actx.tool_ctx.citation_whitelist.add(key)
        actx.tool_ctx.citation_sources[key] = {
            "source": paper.source,
            "external_id": paper.external_id,
            "title": paper.title,
            "url": paper.url,
        }
        remaining = 28_000
        blocks: list[str] = [
            f"Paper: {paper.title}",
            f"Citation key: {key}",
            "Selected section kinds: "
            + ", ".join(dict.fromkeys(section.kind.value for section in sections)),
        ]
        for section in sections:
            header = (
                f"\n[SECTION id={section.id} seq={section.seq} "
                f"kind={section.kind.value} heading={section.heading!r}]\n"
            )
            if remaining <= len(header):
                break
            body = section.body[: max(0, remaining - len(header))]
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
        parsed = json.loads(output_text)
        mission, paper, sections = await self._context(actx)
        section_map = {str(section.id): section for section in sections}
        claims: list[dict] = []
        grounded = 0
        for raw in list(parsed.get("claims") or [])[:200]:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "").strip()
            section_id = str(raw.get("section_id") or "")
            quote = str(raw.get("quote") or "").strip()
            section = section_map.get(section_id)
            evidence_ok = section is not None and bool(quote) and quote in section.body
            if evidence_ok:
                grounded += 1
            claims.append(
                {
                    "text": text,
                    "section_id": section_id if evidence_ok else None,
                    "section_seq": section.seq if evidence_ok and section is not None else None,
                    "heading": section.heading if evidence_ok and section is not None else None,
                    "quote": quote if evidence_ok else "",
                    "inference": bool(raw.get("inference", False)),
                    "evidence_status": "grounded" if evidence_ok else "needs_evidence",
                }
            )
        card = await actx.db.scalar(
            select(ReadingCard).where(
                ReadingCard.mission_id == mission.id,
                ReadingCard.paper_id == paper.id,
            )
        )
        if card is None:
            card = ReadingCard(
                project_id=actx.project_id,
                mission_id=mission.id,
                paper_id=paper.id,
                created_by=actx.actor.id,
                updated_by=actx.actor.id,
            )
            actx.db.add(card)
        else:
            card.version += 1
        card.summary = str(parsed.get("summary") or "").strip()
        card.research_question = str(parsed.get("research_question") or "").strip()
        card.reading_focus_json = list(dict.fromkeys(section.kind.value for section in sections))
        card.method_flow_json = _strings(parsed.get("method_flow"))
        card.experimental_setup_json = _strings(parsed.get("experimental_setup"))
        card.key_results_json = _strings(parsed.get("key_results"))
        card.conclusions_json = _strings(parsed.get("conclusions"))
        card.strengths_json = _strings(parsed.get("strengths"))
        card.limitations_json = _strings(parsed.get("limitations"))
        card.reproducibility_json = _strings(parsed.get("reproducibility"))
        card.github_repositories_json = _grounded_items(
            parsed.get("github_repositories"), section_map, blank_fields=("url",)
        )
        card.paper_ideas_json = _grounded_items(parsed.get("paper_ideas"), section_map)
        card.benchmarks_json = _grounded_items(parsed.get("benchmarks"), section_map)
        card.ablation_findings_json = _grounded_items(parsed.get("ablation_findings"), section_map)
        card.knowledge_tuples_json = _grounded_items(parsed.get("knowledge_tuples"), section_map)
        card.claims_json = claims
        card.status = "needs_review"
        card.generated_by_run_id = actx.run.id
        card.updated_by = actx.actor.id
        card.reviewed_at = None
        await record_card_version(
            actx.db,
            card,
            actor_id=actx.actor.id,
            source_type="agent",
            source_run_id=actx.run.id,
        )
        tuple_count = await index_reading_card_tuples(actx.db, card, sections=sections)
        actx.db.add(
            MissionEvent(
                project_id=actx.project_id,
                mission_id=mission.id,
                event_type="reading_card.generated",
                summary=f"Agent 生成《{paper.title}》阅读卡 v{card.version}",
                step_kind=mission.current_step,
                payload_json={
                    "paper_id": str(paper.id),
                    "card_id": str(card.id),
                    "agent_run_id": str(actx.run.id),
                    "grounded_claims": grounded,
                    "claim_count": len(claims),
                },
                actor_id=actx.actor.id,
            )
        )
        key = f"{paper.source}:{paper.external_id}"
        citations = [citation_sources[key]] if key in citation_sources else []
        return (
            {
                "message": f"Reading card v{card.version} generated for human review.",
                "reading_card_id": str(card.id),
                "reading_card_version": card.version,
                "grounded_claims": grounded,
                "claim_count": len(claims),
                "tuple_count": tuple_count,
                "benchmark_count": len(card.benchmarks_json),
                "idea_count": len(card.paper_ideas_json),
                "citations": [key],
            },
            citations,
        )


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:100] if str(item).strip()]


def _grounded_items(
    value: object,
    section_map: dict[str, PaperSection],
    *,
    blank_fields: tuple[str, ...] = (),
) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for raw in value[:500]:
        if not isinstance(raw, dict):
            continue
        item = {str(key): val for key, val in raw.items()}
        section_id = str(item.get("section_id") or "")
        quote = str(item.get("quote") or "").strip()
        section = section_map.get(section_id)
        grounded = section is not None and bool(quote) and quote in section.body
        item["section_id"] = section_id if grounded else None
        item["section_seq"] = section.seq if grounded and section is not None else None
        item["quote"] = quote if grounded else ""
        inference = bool(item.get("inference", False))
        item["inference"] = inference
        item["evidence_status"] = (
            "context_grounded"
            if grounded and inference
            else "reported"
            if grounded
            else "needs_evidence"
        )
        if not grounded and not inference:
            for field in blank_fields:
                item[field] = ""
        items.append(item)
    return items
