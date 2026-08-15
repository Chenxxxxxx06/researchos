"""Gap-matrix idea generation: mine method x problem gaps, propose ideas.

The matrix mining is deterministic (TF-IDF over library docs); one bounded LLM
call proposes ideas for underexplored cells. Supporting citations are validated
against the library key set before persisting, so no fabricated references.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import AppError
from researchos.common.rate_limit import enforce_rate_limit
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.knowledge.models import ReadingCard
from researchos.projects.service import ProjectService

from .enums import IdeaStatus, PaperSectionKind
from .models import Idea
from .ranking import tokenize
from .repository import IdeaRepository, PaperRepository, PaperSectionRepository

logger = structlog.get_logger(__name__)

_CORPUS_LIMIT = 200
_AXIS_TERMS = 25
_MIN_TERM_SUPPORT = 2
_MAX_GAP_CELLS = 10
_MAX_CONTEXT_PAPERS = 20
_MAX_CONTEXT_CHARS = 28_000
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

GAP_IDEAS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "gap_type": {"type": "string"},
                    "supporting_paper_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title", "description", "supporting_paper_keys"],
            },
        }
    },
    "required": ["ideas"],
}

_SYSTEM_PROMPT = (
    "You are a research ideation assistant. Compare the structured evidence "
    "summaries across papers and propose concrete, falsifiable directions for "
    "underexplored method x problem cells. Treat a missing combination as a "
    "candidate gap, not proof of novelty. Preserve reported limitations and "
    "contradictory results. Cite ONLY paper keys listed in the provided context; "
    "never invent citations. Respond with JSON matching the schema."
)


class LibraryTooSmallError(AppError):
    code = "library_too_small"
    http_status = 409
    message = "At least 5 library papers are required to generate ideas."


@dataclass
class GapDoc:
    key: str
    title: str
    method_terms: set[str]
    problem_terms: set[str]


@dataclass
class GapCell:
    method: str
    problem: str
    weight: int


@dataclass
class GapMatrix:
    method_terms: list[str]
    problem_terms: list[str]
    method_support: dict[str, int]
    problem_support: dict[str, int]
    gaps: list[GapCell]


def _terms_of(text: str) -> set[str]:
    tokens = tokenize(text)
    bigrams = {f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False)}
    return set(tokens) | bigrams


def first_sentences(text: str, count: int = 2) -> str:
    parts = _SENTENCE_RE.split(text.strip())
    return " ".join(parts[:count])


def _axis_top_terms(docs: list[set[str]]) -> tuple[list[str], dict[str, int]]:
    """Top TF-IDF-weighted terms present in >=2 docs; deterministic order."""

    import math

    n = len(docs)
    df: dict[str, int] = {}
    for doc in docs:
        for term in doc:
            df[term] = df.get(term, 0) + 1
    scored: list[tuple[float, str]] = []
    for term, count in df.items():
        if count < _MIN_TERM_SUPPORT:
            continue
        idf = math.log((n + 1) / (count + 1)) + 1.0
        scored.append((count * idf, term))
    scored.sort(key=lambda item: (-item[0], item[1]))
    top = [term for _, term in scored[:_AXIS_TERMS]]
    return top, {term: df[term] for term in top}


def build_gap_matrix(docs: list[GapDoc]) -> GapMatrix:
    method_terms, method_support = _axis_top_terms([d.method_terms for d in docs])
    problem_terms, problem_support = _axis_top_terms([d.problem_terms for d in docs])

    covered: set[tuple[str, str]] = set()
    for doc in docs:
        for m in method_terms:
            if m not in doc.method_terms:
                continue
            for p in problem_terms:
                if p in doc.problem_terms:
                    covered.add((m, p))

    gaps = [
        GapCell(m, p, method_support[m] * problem_support[p])
        for m in method_terms
        for p in problem_terms
        if (m, p) not in covered
    ]
    gaps.sort(key=lambda cell: (-cell.weight, cell.method, cell.problem))
    return GapMatrix(
        method_terms=method_terms,
        problem_terms=problem_terms,
        method_support=method_support,
        problem_support=problem_support,
        gaps=gaps[:_MAX_GAP_CELLS],
    )


class GapMatrixService:
    def __init__(self, db: AsyncSession, *, llm_provider=None) -> None:
        self.db = db
        self.papers = PaperRepository(db)
        self.sections = PaperSectionRepository(db)
        self.ideas = IdeaRepository(db)
        self.projects = ProjectService(db)
        self._llm_provider = llm_provider

    async def _latest_cards(self, project_id: uuid.UUID) -> dict[uuid.UUID, ReadingCard]:
        cards = list(
            (
                await self.db.execute(
                    select(ReadingCard)
                    .where(ReadingCard.project_id == project_id)
                    .order_by(ReadingCard.updated_at.desc(), ReadingCard.id)
                )
            )
            .scalars()
            .all()
        )
        latest: dict[uuid.UUID, ReadingCard] = {}
        for card in cards:
            latest.setdefault(card.paper_id, card)
        return latest

    async def _build_docs(
        self,
        project_id: uuid.UUID,
        cards: dict[uuid.UUID, ReadingCard] | None = None,
    ) -> list[GapDoc]:
        papers = await self.papers.list_recent(project_id, limit=_CORPUS_LIMIT)
        cards = cards if cards is not None else await self._latest_cards(project_id)
        method_bodies: dict[uuid.UUID, list[str]] = {}
        for section in await self.sections.list_for_papers_by_kind(
            [p.id for p in papers], PaperSectionKind.METHOD
        ):
            method_bodies.setdefault(section.paper_id, []).append(section.body)
        docs: list[GapDoc] = []
        for paper in papers:
            card = cards.get(paper.id)
            method_doc = (
                " ".join(
                    [
                        *method_bodies.get(paper.id, []),
                        *_card_strings(card, "method_flow_json"),
                        *_card_strings(card, "experimental_setup_json"),
                        *_card_strings(card, "key_results_json"),
                        *_card_strings(card, "limitations_json"),
                    ]
                ).strip()
                or paper.title
            )
            problem_doc = " ".join(
                [
                    first_sentences(paper.abstract or ""),
                    paper.title,
                    card.research_question if card is not None else "",
                    *_card_strings(card, "conclusions_json"),
                ]
            ).strip()
            docs.append(
                GapDoc(
                    key=f"{paper.source}:{paper.external_id}",
                    title=paper.title,
                    method_terms=_terms_of(method_doc),
                    problem_terms=_terms_of(problem_doc),
                )
            )
        return docs

    async def generate(
        self, actor: User, project_id: uuid.UUID, *, max_ideas: int
    ) -> tuple[list[Idea], int, int]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        await enforce_rate_limit(f"idea_generate:{actor.id}", limit=5)

        papers = await self.papers.list_recent(project_id, limit=_CORPUS_LIMIT)
        if len(papers) < 5:
            raise LibraryTooSmallError()

        cards = await self._latest_cards(project_id)
        docs = await self._build_docs(project_id, cards)
        matrix = build_gap_matrix(docs)

        context_papers = _bounded_evidence_context(papers, cards)
        raw_ideas = await self._call_llm(project_id, matrix, context_papers, max_ideas)

        library_keys = await self.papers.list_ids_for_project(project_id)
        created: list[Idea] = []
        for index, raw in enumerate(raw_ideas[:max_ideas]):
            if not isinstance(raw, dict):
                continue
            keys = [
                key
                for key in raw.get("supporting_paper_keys") or []
                if isinstance(key, str) and key in library_keys
            ]
            if not keys:
                continue  # zero valid citations -> dropped, no fabrication
            title = str(raw.get("title") or "").strip()[:300]
            if not title:
                continue
            metadata: dict = {
                "generated": True,
                "gap_type": str(raw.get("gap_type") or "coverage"),
                "supporting_paper_keys": keys,
                "evidence_basis": "reading_cards+parsed_sections",
                "reading_cards_used": len(cards),
            }
            if index < len(matrix.gaps):
                cell = matrix.gaps[index]
                metadata["cell"] = [cell.method, cell.problem]
            created.append(
                await self.ideas.create(
                    Idea(
                        project_id=project_id,
                        title=title,
                        description=str(raw.get("description") or ""),
                        hypothesis=(str(raw["hypothesis"]) if raw.get("hypothesis") else None),
                        status=IdeaStatus.DRAFT,
                        metadata_json=metadata,
                        created_by=actor.id,
                    )
                )
            )
        await self.db.commit()
        for idea in created:
            await self.db.refresh(idea)
        return created, len(matrix.gaps), len(papers)

    async def _call_llm(
        self,
        project_id: uuid.UUID,
        matrix: GapMatrix,
        context_papers: list[dict],
        max_ideas: int,
    ) -> list[dict]:
        # Lazy import: the LLM layer is another partition's module surface.
        from researchos.agents.llm.base import LLMMessage, TextDelta
        from researchos.agents.llm.factory import get_llm_provider

        provider = self._llm_provider or await get_llm_provider(project_id)

        user_payload = {
            "max_ideas": max_ideas,
            "method_terms": matrix.method_terms,
            "problem_terms": matrix.problem_terms,
            "gap_cells": [
                {"method": cell.method, "problem": cell.problem, "weight": cell.weight}
                for cell in matrix.gaps
            ],
        }
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            # Tool-shaped context: the mock provider's citation extractor reads
            # {"results": [{source, external_id, ...}]} from tool messages.
            LLMMessage(
                role="tool",
                content=json.dumps({"results": context_papers}),
                name="library.context",
                tool_call_id="gap_context_1",
            ),
            LLMMessage(
                role="user",
                content=(
                    "Propose ideas for the most promising gap cells.\n" + json.dumps(user_payload)
                ),
            ),
        ]

        text_parts: list[str] = []
        async for event in provider.stream(
            messages=messages, tools=None, response_schema=GAP_IDEAS_SCHEMA
        ):
            if isinstance(event, TextDelta):
                text_parts.append(event.text)
        raw_text = "".join(text_parts).strip()
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("gap_ideas_unparseable", raw_length=len(raw_text))
            return []
        ideas = parsed.get("ideas") if isinstance(parsed, dict) else None
        return ideas if isinstance(ideas, list) else []


def _card_strings(card: ReadingCard | None, field: str, *, limit: int = 2) -> list[str]:
    if card is None:
        return []
    value = getattr(card, field, None)
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:300] for item in value[:limit] if str(item).strip()]


def _paper_evidence(paper, card: ReadingCard | None) -> dict:  # noqa: ANN001
    result: dict = {
        "source": paper.source,
        "external_id": paper.external_id,
        "title": paper.title,
        "abstract": first_sentences(paper.abstract or "", count=3)[:800],
    }
    if card is None:
        return result
    result["reading_card"] = {
        "status": card.status,
        "summary": card.summary[:1200],
        "research_question": card.research_question[:500],
        "method_flow": _card_strings(card, "method_flow_json"),
        "experimental_setup": _card_strings(card, "experimental_setup_json"),
        "key_results": _card_strings(card, "key_results_json"),
        "conclusions": _card_strings(card, "conclusions_json"),
        "limitations": _card_strings(card, "limitations_json"),
    }
    return result


def _bounded_evidence_context(papers: list, cards: dict[uuid.UUID, ReadingCard]) -> list[dict]:
    context: list[dict] = []
    used = 0
    for paper in papers[:_MAX_CONTEXT_PAPERS]:
        item = _paper_evidence(paper, cards.get(paper.id))
        size = len(json.dumps(item, ensure_ascii=False))
        if used + size > _MAX_CONTEXT_CHARS:
            item = {
                "source": paper.source,
                "external_id": paper.external_id,
                "title": paper.title,
            }
            size = len(json.dumps(item, ensure_ascii=False))
        if used + size > _MAX_CONTEXT_CHARS:
            break
        context.append(item)
        used += size
    return context
