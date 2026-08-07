"""Deterministic incremental chunking and local vector indexing.

The default hashing embedding is deliberately transparent and dependency-free:
it provides real pgvector retrieval in offline/local deployments. A later
provider adapter can replace vectors without changing the chunk contract.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections import Counter

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.research.models import Paper, PaperSection

from .models import PaperChunk

EMBEDDING_DIMENSIONS = 384
EMBEDDING_MODEL = "hashing-384-v1"
_WORD_RE = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*|[\u4e00-\u9fff]+")


def embedding_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", raw):
            if len(raw) == 1:
                tokens.append(raw)
            else:
                tokens.extend(raw[index : index + 2] for index in range(len(raw) - 1))
        elif len(raw) >= 2:
            tokens.append(raw)
    return tokens


def hashing_embedding(text: str) -> list[float]:
    """Feature-hashing vector with signed buckets and L2 normalization."""

    counts = Counter(embedding_tokens(text))
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def split_text(text: str, *, size: int = 1800, overlap: int = 240) -> list[tuple[int, int, str]]:
    """Split text on nearby whitespace with stable character offsets."""

    normalized = text.strip()
    if not normalized:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(normalized):
        target = min(len(normalized), start + size)
        end = target
        if target < len(normalized):
            boundary = max(
                normalized.rfind("\n", start + size // 2, target),
                normalized.rfind(" ", start + size // 2, target),
            )
            if boundary > start:
                end = boundary
        content = normalized[start:end].strip()
        if content:
            actual_start = normalized.find(content, start, end + 1)
            chunks.append((actual_start, actual_start + len(content), content))
        if end >= len(normalized):
            break
        next_start = max(start + 1, end - overlap)
        while next_start < end and not normalized[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


async def index_paper_sections(db: AsyncSession, paper: Paper) -> int:
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
    rows: list[PaperChunk] = []
    for section in sections:
        for chunk_index, (char_start, char_end, content) in enumerate(split_text(section.body)):
            rows.append(
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
                    embedding=hashing_embedding(f"{paper.title} {section.heading} {content}"),
                    embedding_model=EMBEDDING_MODEL,
                )
            )
    db.add_all(rows)
    await db.flush()
    return len(rows)


async def ensure_project_chunks(
    db: AsyncSession, project_id: uuid.UUID, *, limit: int = 100
) -> tuple[int, int]:
    """Incrementally index papers that have parsed sections but no chunks."""

    has_sections = exists(select(PaperSection.id).where(PaperSection.paper_id == Paper.id))
    has_chunks = exists(select(PaperChunk.id).where(PaperChunk.paper_id == Paper.id))
    papers = list(
        (
            await db.execute(
                select(Paper)
                .where(Paper.project_id == project_id, has_sections, ~has_chunks)
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
