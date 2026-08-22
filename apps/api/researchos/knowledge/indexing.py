"""Sentence-aligned chunking and profile-driven vector indexing.

Chunking is parameterized by the active embedding profile (token budgets are
approximated in characters, see ``profiles.py``). Chunks align to sentence
boundaries and carry exact ``char_start``/``char_end`` offsets into
``PaperSection.body`` — the single source of truth for quote verification.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.research.models import Paper, PaperSection

from .embeddings import embed_texts, embedding_tokens
from .models import PaperChunk, PaperKnowledgeTuple, ReadingCard
from .profiles import EmbeddingProfile, get_active_profile

# A sentence ends at terminal punctuation followed by whitespace, right after
# CJK terminal punctuation (Chinese prose has no inter-sentence spaces), or at
# a newline boundary. Terminal punctuation stays attached to its sentence.
_BOUNDARY_RE = re.compile(r"(?<=[.?!])\s+|(?<=[。！？])\s*|\n+")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Whitespace-trimmed ``(start, end)`` spans of each sentence in ``text``."""

    spans: list[tuple[int, int]] = []
    prev = 0
    for match in _BOUNDARY_RE.finditer(text):
        span = _trimmed(text, prev, match.start())
        if span is not None:
            spans.append(span)
        prev = match.end()
    tail = _trimmed(text, prev, len(text))
    if tail is not None:
        spans.append(tail)
    return spans


def _trimmed(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _hard_split(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Split an overlong sentence at word boundaries into <= ``max_chars`` pieces."""

    pieces: list[tuple[int, int]] = []
    pos = start
    while pos < end:
        cut = min(end, pos + max_chars)
        if cut < end:
            boundary = text.rfind(" ", pos + max_chars // 2, cut)
            if boundary > pos:
                cut = boundary
        piece = _trimmed(text, pos, cut)
        if piece is not None:
            pieces.append(piece)
        pos = max(cut, piece[1] if piece else pos + 1)
        while pos < end and text[pos].isspace():
            pos += 1
    return pieces


def split_text(text: str, profile: EmbeddingProfile) -> list[tuple[int, int, str]]:
    """Sentence-aligned chunks with exact offsets into ``text``.

    Sentences are packed greedily up to the profile's max budget; the next
    chunk re-includes trailing whole sentences up to the overlap budget.
    A single sentence longer than the max budget falls back to word-aligned
    hard splitting. Invariant: ``text[start:end] == content`` for every chunk.
    """

    if not text.strip():
        return []
    max_chars = int(profile.chunk_max_tokens * profile.chars_per_token)
    overlap_chars = int(profile.chunk_overlap_tokens * profile.chars_per_token)
    pieces: list[tuple[int, int]] = []
    for start, end in _sentence_spans(text):
        if end - start <= max_chars:
            pieces.append((start, end))
        else:
            pieces.extend(_hard_split(text, start, end, max_chars))
    chunks: list[tuple[int, int, str]] = []
    covered = -1  # highest piece index already emitted in a chunk
    index = 0
    while index < len(pieces):
        start = pieces[index][0]
        last = index
        while last + 1 < len(pieces) and pieces[last + 1][1] - start <= max_chars:
            last += 1
        if last > covered:
            end = pieces[last][1]
            chunks.append((start, end, text[start:end]))
            covered = last
        if last == len(pieces) - 1:
            break
        # Whole-sentence overlap: walk back from the chunk end while the
        # re-covered span stays within the overlap budget.
        next_index = last + 1
        if pieces[last][1] - pieces[last][0] <= overlap_chars:
            next_index = last
            back = last
            while back > index and pieces[last][1] - pieces[back - 1][0] <= overlap_chars:
                back -= 1
                next_index = back
        # Forward progress always wins over overlap (a tiny chunk that fits
        # the whole overlap budget cannot be re-covered entirely).
        index = max(next_index, index + 1)
    return chunks


async def index_paper_sections(db: AsyncSession, paper: Paper) -> int:
    profile = get_active_profile()
    sections = list(
        (
            await db.execute(
                select(PaperSection)
                .where(PaperSection.paper_id == paper.id)
                .order_by(PaperSection.seq.asc())
            )
        )
        .scalars()
        .all()
    )
    await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper.id))
    planned: list[tuple[PaperSection, int, int, int, str]] = []
    for section in sections:
        for chunk_index, (char_start, char_end, content) in enumerate(
            split_text(section.body, profile)
        ):
            planned.append((section, chunk_index, char_start, char_end, content))
    vectors = await embed_texts(
        [f"{paper.title} {section.heading} {content}" for section, _, _, _, content in planned],
        profile,
    )
    rows = [
        PaperChunk(
            project_id=paper.project_id,
            paper_id=paper.id,
            section_id=section.id,
            section_seq=section.seq,
            chunk_index=chunk_index,
            heading=section.heading,
            section_kind=section.kind.value,
            content=content,
            char_start=char_start,
            char_end=char_end,
            token_count=len(embedding_tokens(content)),
            embedding=vector,
            embedding_model=profile.name,
        )
        for (section, chunk_index, char_start, char_end, content), vector in zip(
            planned, vectors, strict=True
        )
    ]
    db.add_all(rows)
    await db.flush()
    return len(rows)


async def index_reading_card_tuples(
    db: AsyncSession,
    card: ReadingCard,
    *,
    sections: list[PaperSection] | None = None,
) -> int:
    """Replace the tuple index for one reading-card version.

    Evidence section ids and quotes are verified against the canonical paper
    sections before entering retrieval. Ungrounded tuples remain useful as
    hypotheses, but carry no section id or quote and must not be presented as
    observed evidence.
    """

    profile = get_active_profile()
    if sections is None:
        sections = list(
            (
                await db.execute(
                    select(PaperSection)
                    .where(PaperSection.paper_id == card.paper_id)
                    .order_by(PaperSection.seq.asc())
                )
            )
            .scalars()
            .all()
        )
    section_map = {str(section.id): section for section in sections}
    normalized: list[dict] = []
    for raw in list(card.knowledge_tuples_json or [])[:500]:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "claim").strip().lower()[:32]
        head = str(raw.get("head") or "").strip()[:500]
        relation = str(raw.get("relation") or "").strip()[:160]
        tail = str(raw.get("tail") or "").strip()
        if not head or not relation or not tail:
            continue
        raw_section_id = str(raw.get("section_id") or "")
        quote = str(raw.get("quote") or "").strip()
        section = section_map.get(raw_section_id)
        grounded = section is not None and bool(quote) and quote in section.body
        inference = bool(raw.get("inference", False))
        evidence_status = (
            "context_grounded"
            if grounded and inference
            else "reported"
            if grounded
            else "needs_evidence"
        )
        content = f"{kind}: {head} {relation} {tail}"
        if grounded:
            content += f" Evidence: {quote}"
        normalized.append(
            {
                "kind": kind,
                "head": head,
                "relation": relation,
                "tail": tail,
                "section_id": section.id if grounded and section is not None else None,
                "quote": quote if grounded else "",
                "inference": inference,
                "evidence_status": evidence_status,
                "content": content,
            }
        )

    await db.execute(
        delete(PaperKnowledgeTuple).where(PaperKnowledgeTuple.reading_card_id == card.id)
    )
    vectors = await embed_texts([item["content"] for item in normalized], profile)
    db.add_all(
        PaperKnowledgeTuple(
            project_id=card.project_id,
            mission_id=card.mission_id,
            paper_id=card.paper_id,
            reading_card_id=card.id,
            section_id=item["section_id"],
            tuple_index=index,
            tuple_kind=item["kind"],
            head=item["head"],
            relation=item["relation"],
            tail=item["tail"],
            evidence_quote=item["quote"],
            is_inference=item["inference"],
            evidence_status=item["evidence_status"],
            content=item["content"],
            embedding=vector,
            embedding_model=profile.name,
        )
        for index, (item, vector) in enumerate(zip(normalized, vectors, strict=True))
    )
    await db.flush()
    return len(normalized)


async def ensure_project_tuples(
    db: AsyncSession, project_id: uuid.UUID, *, limit: int = 100
) -> tuple[int, int]:
    """Rebuild tuple embeddings after profile changes or missing index rows."""

    profile = get_active_profile()
    cards = list(
        (
            await db.execute(
                select(ReadingCard)
                .where(ReadingCard.project_id == project_id)
                .order_by(ReadingCard.updated_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    rebuilt = 0
    tuple_count = 0
    for card in cards:
        expected = len(
            [
                item
                for item in (card.knowledge_tuples_json or [])
                if isinstance(item, dict)
                and str(item.get("head") or "").strip()
                and str(item.get("relation") or "").strip()
                and str(item.get("tail") or "").strip()
            ]
        )
        stored = list(
            (
                await db.execute(
                    select(PaperKnowledgeTuple).where(
                        PaperKnowledgeTuple.reading_card_id == card.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if expected != len(stored) or any(item.embedding_model != profile.name for item in stored):
            tuple_count += await index_reading_card_tuples(db, card)
            rebuilt += 1
    if rebuilt:
        await db.commit()
    return rebuilt, tuple_count


async def ensure_project_chunks(
    db: AsyncSession, project_id: uuid.UUID, *, limit: int = 100
) -> tuple[int, int]:
    """Incrementally index papers whose chunks are missing or stale.

    A paper is (re)indexed when it has parsed sections but no chunks, or when
    its chunks were built under a different embedding profile — a profile
    change invalidates the whole index.
    """

    profile = get_active_profile()
    has_sections = exists(select(PaperSection.id).where(PaperSection.paper_id == Paper.id))
    has_chunks = exists(select(PaperChunk.id).where(PaperChunk.paper_id == Paper.id))
    stale_profile = exists(
        select(PaperChunk.id).where(
            PaperChunk.paper_id == Paper.id,
            PaperChunk.embedding_model != profile.name,
        )
    )
    papers = list(
        (
            await db.execute(
                select(Paper)
                .where(
                    Paper.project_id == project_id,
                    has_sections,
                    or_(~has_chunks, stale_profile),
                )
                .order_by(Paper.created_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    chunk_count = 0
    for paper in papers:
        chunk_count += await index_paper_sections(db, paper)
    if papers:
        await db.commit()
    return len(papers), chunk_count
