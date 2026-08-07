"""Business logic for mission paper sets, reading artifacts, and grounded retrieval."""

from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from math import sqrt

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.missions.repository import MissionRepository
from researchos.projects.service import ProjectService
from researchos.research.models import Paper, PaperSection

from .indexing import EMBEDDING_MODEL, ensure_project_chunks, hashing_embedding
from .models import (
    MissionPaper,
    MissionTopicCluster,
    PaperChunk,
    ReadingCard,
    ReadingCardVersion,
    ReadingNote,
)
from .schemas import (
    AddMissionPapersRequest,
    MissionPaperResponse,
    RagHitResponse,
    RagSearchRequest,
    RagSearchResponse,
    ReadingCardUpsertRequest,
    ReadingNoteCreateRequest,
    ReadingNoteUpdateRequest,
    UpdateTopicClusterRequest,
)

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff-]+", re.UNICODE)


class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.missions = MissionRepository(db)

    async def _mission(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID, *, write: bool
    ) -> ResearchMission:
        await ProjectService(self.db).ensure_access(
            actor, project_id, ProjectRole.RESEARCHER if write else ProjectRole.VIEWER
        )
        mission = await self.missions.get(project_id, mission_id)
        if mission is None:
            raise NotFoundError("Research mission not found.")
        return mission

    async def _paper(self, project_id: uuid.UUID, paper_id: uuid.UUID) -> Paper:
        paper = await self.db.get(Paper, paper_id)
        if paper is None or paper.project_id != project_id:
            raise NotFoundError("Paper not found.")
        return paper

    async def add_papers(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: AddMissionPapersRequest,
    ) -> list[MissionPaperResponse]:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        unique_ids = list(dict.fromkeys(payload.paper_ids))
        papers = list(
            (
                await self.db.execute(
                    select(Paper).where(Paper.project_id == project_id, Paper.id.in_(unique_ids))
                )
            )
            .scalars()
            .all()
        )
        if len(papers) != len(unique_ids):
            raise NotFoundError("One or more papers were not found in this project.")
        existing = set(
            (
                await self.db.execute(
                    select(MissionPaper.paper_id).where(
                        MissionPaper.mission_id == mission_id,
                        MissionPaper.paper_id.in_(unique_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        for paper in papers:
            if paper.id not in existing:
                self.db.add(
                    MissionPaper(
                        project_id=project_id,
                        mission_id=mission_id,
                        paper_id=paper.id,
                        inclusion_reason=payload.inclusion_reason,
                        included_by=actor.id,
                    )
                )
        mission.last_activity_at = datetime.now(tz=UTC)
        mission.updated_by = actor.id
        self.db.add(
            MissionEvent(
                project_id=project_id,
                mission_id=mission_id,
                event_type="papers.included",
                summary=f"纳入 {len(papers) - len(existing)} 篇论文",
                step_kind=mission.current_step,
                payload_json={"paper_ids": [str(item.id) for item in papers]},
                actor_id=actor.id,
            )
        )
        await self.db.commit()
        return await self.list_papers(actor, project_id, mission_id)

    async def list_papers(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[MissionPaperResponse]:
        await self._mission(actor, project_id, mission_id, write=False)
        rows = (
            await self.db.execute(
                select(MissionPaper, Paper)
                .join(Paper, Paper.id == MissionPaper.paper_id)
                .where(MissionPaper.mission_id == mission_id)
                .order_by(Paper.published_at.desc().nullslast(), Paper.title.asc())
            )
        ).all()
        return [
            MissionPaperResponse(
                id=link.id,
                paper_id=paper.id,
                cluster_id=link.cluster_id,
                relevance_score=link.relevance_score,
                inclusion_reason=link.inclusion_reason,
                title=paper.title,
                authors=paper.authors_json,
                venue=paper.venue,
                published_at=paper.published_at,
                ingest_status=paper.ingest_status,
            )
            for link, paper in rows
        ]

    async def cluster(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[tuple[MissionTopicCluster, int]]:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        rows = (
            await self.db.execute(
                select(MissionPaper, Paper)
                .join(Paper, Paper.id == MissionPaper.paper_id)
                .where(MissionPaper.mission_id == mission_id)
            )
        ).all()
        if not rows:
            raise ValidationError("Include papers before creating topic clusters.")
        await self.db.execute(
            update(MissionPaper)
            .where(MissionPaper.mission_id == mission_id)
            .values(cluster_id=None)
        )
        await self.db.execute(
            delete(MissionTopicCluster).where(MissionTopicCluster.mission_id == mission_id)
        )
        vectors = {
            paper.id: hashing_embedding(f"{paper.title} {paper.abstract or ''}")
            for _, paper in rows
        }
        groups: list[list[tuple[MissionPaper, Paper]]] = [[(link, paper)] for link, paper in rows]
        target = 1 if len(rows) == 1 else max(2, min(8, round(sqrt(len(rows)))))
        while len(groups) > 1:
            best: tuple[float, int, int] | None = None
            for left in range(len(groups)):
                for right in range(left + 1, len(groups)):
                    similarities = [
                        _cosine(vectors[a.id], vectors[b.id])
                        for _, a in groups[left]
                        for _, b in groups[right]
                    ]
                    similarity = sum(similarities) / len(similarities)
                    candidate = (similarity, left, right)
                    if best is None or candidate > best:
                        best = candidate
            assert best is not None
            similarity, left, right = best
            if len(groups) <= target and similarity < 0.28:
                break
            groups[left].extend(groups.pop(right))
        created: list[tuple[MissionTopicCluster, int]] = []
        groups.sort(key=lambda group: (-len(group), min(str(paper.id) for _, paper in group)))
        for position, group in enumerate(groups):
            links = [link for link, _ in group]
            papers = [paper for _, paper in group]
            name, cluster_keywords = _cluster_name(papers)
            cluster = MissionTopicCluster(
                project_id=project_id,
                mission_id=mission_id,
                name=name,
                summary=(
                    f"Embedding-based average-linkage cluster containing {len(links)} "
                    "included paper(s)."
                ),
                keywords_json=cluster_keywords,
                algorithm="hashing-384-agglomerative-v1",
                status="generated",
                position=position,
                created_by=actor.id,
                updated_by=actor.id,
            )
            self.db.add(cluster)
            await self.db.flush()
            for link in links:
                link.cluster_id = cluster.id
            created.append((cluster, len(links)))
        self.db.add(
            MissionEvent(
                project_id=project_id,
                mission_id=mission_id,
                event_type="clusters.generated",
                summary=f"生成 {len(created)} 个可编辑主题簇",
                step_kind=mission.current_step,
                payload_json={
                    "cluster_count": len(created),
                    "method": "hashing-384-agglomerative-v1",
                    "threshold": 0.28,
                },
                actor_id=actor.id,
            )
        )
        await self.db.commit()
        return created

    async def list_clusters(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[tuple[MissionTopicCluster, int]]:
        await self._mission(actor, project_id, mission_id, write=False)
        rows = await self.db.execute(
            select(MissionTopicCluster, func.count(MissionPaper.id))
            .outerjoin(MissionPaper, MissionPaper.cluster_id == MissionTopicCluster.id)
            .where(MissionTopicCluster.mission_id == mission_id)
            .group_by(MissionTopicCluster.id)
            .order_by(MissionTopicCluster.position.asc())
        )
        return [(cluster, int(count)) for cluster, count in rows.all()]

    async def update_cluster(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        cluster_id: uuid.UUID,
        payload: UpdateTopicClusterRequest,
    ) -> MissionTopicCluster:
        await self._mission(actor, project_id, mission_id, write=True)
        cluster = await self.db.get(MissionTopicCluster, cluster_id)
        if cluster is None or cluster.mission_id != mission_id:
            raise NotFoundError("Topic cluster not found.")
        if cluster.version != payload.expected_version:
            raise ConflictError(
                "Topic cluster changed elsewhere.", code="topic_cluster_version_conflict"
            )
        if payload.name is not None:
            cluster.name = payload.name.strip()
        if payload.summary is not None:
            cluster.summary = payload.summary.strip()
        if payload.keywords is not None:
            cluster.keywords_json = [item.strip() for item in payload.keywords if item.strip()]
        cluster.version += 1
        cluster.updated_by = actor.id
        await self.db.commit()
        await self.db.refresh(cluster)
        return cluster

    async def upsert_card(
        self,
        actor: User,
        project_id: uuid.UUID,
        paper_id: uuid.UUID,
        payload: ReadingCardUpsertRequest,
    ) -> ReadingCard:
        await self._mission(actor, project_id, payload.mission_id, write=True)
        await self._paper(project_id, paper_id)
        linked = await self.db.scalar(
            select(MissionPaper.id).where(
                MissionPaper.mission_id == payload.mission_id,
                MissionPaper.paper_id == paper_id,
            )
        )
        if linked is None:
            raise ValidationError("Include the paper in this mission before saving a reading card.")
        card = await self.db.scalar(
            select(ReadingCard).where(
                ReadingCard.mission_id == payload.mission_id,
                ReadingCard.paper_id == paper_id,
            )
        )
        now = datetime.now(tz=UTC)
        if card is None:
            if payload.expected_version is not None:
                raise ConflictError("Reading card does not exist yet.")
            card = ReadingCard(
                project_id=project_id,
                mission_id=payload.mission_id,
                paper_id=paper_id,
                created_by=actor.id,
                updated_by=actor.id,
            )
            self.db.add(card)
        elif payload.expected_version != card.version:
            raise ConflictError(
                "Reading card changed elsewhere.", code="reading_card_version_conflict"
            )
        card.summary = payload.summary.strip()
        card.research_question = payload.research_question.strip()
        card.method_flow_json = payload.method_flow
        card.strengths_json = payload.strengths
        card.limitations_json = payload.limitations
        card.reproducibility_json = payload.reproducibility
        card.claims_json = payload.claims
        card.status = payload.status
        card.updated_by = actor.id
        if card.id is not None and payload.expected_version is not None:
            card.version += 1
        card.reviewed_at = now if payload.status == "reviewed" else None
        await record_card_version(
            self.db,
            card,
            actor_id=actor.id,
            source_type="human",
            source_run_id=None,
        )
        await self.db.commit()
        await self.db.refresh(card)
        return card

    async def list_card_versions(
        self,
        actor: User,
        project_id: uuid.UUID,
        paper_id: uuid.UUID,
        mission_id: uuid.UUID,
    ) -> list[ReadingCardVersion]:
        await self._mission(actor, project_id, mission_id, write=False)
        await self._paper(project_id, paper_id)
        return list(
            (
                await self.db.execute(
                    select(ReadingCardVersion)
                    .where(
                        ReadingCardVersion.project_id == project_id,
                        ReadingCardVersion.paper_id == paper_id,
                        ReadingCardVersion.mission_id == mission_id,
                    )
                    .order_by(ReadingCardVersion.version.desc())
                )
            )
            .scalars()
            .all()
        )

    async def validate_card_generation(
        self,
        actor: User,
        project_id: uuid.UUID,
        paper_id: uuid.UUID,
        mission_id: uuid.UUID,
        *,
        regenerate: bool,
    ) -> None:
        await self._mission(actor, project_id, mission_id, write=True)
        await self._paper(project_id, paper_id)
        linked = await self.db.scalar(
            select(MissionPaper.id).where(
                MissionPaper.mission_id == mission_id,
                MissionPaper.paper_id == paper_id,
            )
        )
        if linked is None:
            raise ValidationError("Include the paper before generating its reading card.")
        existing = await self.db.scalar(
            select(ReadingCard).where(
                ReadingCard.mission_id == mission_id,
                ReadingCard.paper_id == paper_id,
            )
        )
        if existing is not None and not regenerate:
            raise ConflictError(
                "A reading card already exists. Confirm regeneration to create a new version.",
                code="reading_card_regeneration_confirmation_required",
            )

    async def list_cards(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[ReadingCard]:
        await self._mission(actor, project_id, mission_id, write=False)
        return list(
            (
                await self.db.execute(
                    select(ReadingCard)
                    .where(ReadingCard.mission_id == mission_id)
                    .order_by(ReadingCard.updated_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def create_note(
        self,
        actor: User,
        project_id: uuid.UUID,
        paper_id: uuid.UUID,
        payload: ReadingNoteCreateRequest,
    ) -> ReadingNote:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        await self._paper(project_id, paper_id)
        if payload.mission_id is not None:
            await self._mission(actor, project_id, payload.mission_id, write=True)
        if payload.section_id is not None:
            section = await self.db.get(PaperSection, payload.section_id)
            if section is None or section.paper_id != paper_id:
                raise NotFoundError("Paper section not found.")
        note = ReadingNote(
            project_id=project_id,
            mission_id=payload.mission_id,
            paper_id=paper_id,
            section_id=payload.section_id,
            quote=payload.quote.strip(),
            content=payload.content.strip(),
            tags_json=payload.tags,
            created_by=actor.id,
            updated_by=actor.id,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def list_notes(
        self,
        actor: User,
        project_id: uuid.UUID,
        paper_id: uuid.UUID,
        mission_id: uuid.UUID | None,
    ) -> list[ReadingNote]:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.VIEWER)
        await self._paper(project_id, paper_id)
        where = [ReadingNote.project_id == project_id, ReadingNote.paper_id == paper_id]
        if mission_id is not None:
            where.append(ReadingNote.mission_id == mission_id)
        return list(
            (
                await self.db.execute(
                    select(ReadingNote).where(*where).order_by(ReadingNote.updated_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def update_note(
        self,
        actor: User,
        project_id: uuid.UUID,
        note_id: uuid.UUID,
        payload: ReadingNoteUpdateRequest,
    ) -> ReadingNote:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        note = await self.db.get(ReadingNote, note_id)
        if note is None or note.project_id != project_id:
            raise NotFoundError("Reading note not found.")
        if note.version != payload.expected_version:
            raise ConflictError(
                "Reading note changed elsewhere.", code="reading_note_version_conflict"
            )
        if payload.quote is not None:
            note.quote = payload.quote.strip()
        if payload.content is not None:
            note.content = payload.content.strip()
        if payload.tags is not None:
            note.tags_json = payload.tags
        note.version += 1
        note.updated_by = actor.id
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def delete_note(self, actor: User, project_id: uuid.UUID, note_id: uuid.UUID) -> None:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        note = await self.db.get(ReadingNote, note_id)
        if note is None or note.project_id != project_id:
            raise NotFoundError("Reading note not found.")
        await self.db.delete(note)
        await self.db.commit()

    async def rag_search(
        self, actor: User, project_id: uuid.UUID, payload: RagSearchRequest
    ) -> RagSearchResponse:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.VIEWER)
        if payload.mission_id is not None:
            await self._mission(actor, project_id, payload.mission_id, write=False)
        tokens = _tokens(payload.query)[:12]
        if not tokens:
            raise ValidationError("Search query has no searchable terms.")
        indexed_papers, indexed_chunks = await ensure_project_chunks(self.db, project_id)
        query_vector = hashing_embedding(payload.query)
        distance = PaperChunk.embedding.cosine_distance(query_vector)
        ts_query = func.plainto_tsquery("simple", payload.query)
        keyword_rank = func.ts_rank_cd(PaperChunk.search_tsv, ts_query)
        hybrid_score = (1.0 - distance) * 0.68 + func.least(keyword_rank, 1.0) * 0.32
        statement = (
            select(
                PaperChunk,
                Paper,
                distance.label("vector_distance"),
                keyword_rank.label("keyword_rank"),
                hybrid_score.label("hybrid_score"),
            )
            .join(Paper, Paper.id == PaperChunk.paper_id)
            .where(PaperChunk.project_id == project_id)
        )
        if payload.mission_id is not None:
            statement = statement.join(
                MissionPaper, MissionPaper.paper_id == PaperChunk.paper_id
            ).where(MissionPaper.mission_id == payload.mission_id)
        if payload.kinds:
            statement = statement.where(
                PaperChunk.section_kind.in_([kind.value for kind in payload.kinds])
            )
        rows = (
            await self.db.execute(
                statement.order_by(hybrid_score.desc(), PaperChunk.id.asc()).limit(
                    max(80, payload.limit * 5)
                )
            )
        ).all()
        hits: list[RagHitResponse] = []
        for chunk, paper, raw_distance, raw_keyword, raw_hybrid in rows:
            vector_score = max(-1.0, min(1.0, 1.0 - float(raw_distance or 0.0)))
            normalized_keyword = max(0.0, min(1.0, float(raw_keyword or 0.0)))
            score = max(0.0, min(1.0, float(raw_hybrid or 0.0)))
            hits.append(
                RagHitResponse(
                    chunk_id=chunk.id,
                    paper_id=paper.id,
                    section_id=chunk.section_id,
                    title=paper.title,
                    heading=chunk.heading,
                    kind=chunk.section_kind,
                    snippet=_snippet(chunk.content, tokens),
                    score=round(score, 4),
                    vector_score=round(vector_score, 4),
                    keyword_score=round(normalized_keyword, 4),
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    citation_key=f"{paper.source}:{paper.external_id}",
                )
            )
        return RagSearchResponse(
            query=payload.query,
            mode="hybrid-vector-keyword-v1",
            embedding_model=EMBEDDING_MODEL,
            indexed_papers=indexed_papers,
            indexed_chunks=indexed_chunks,
            hits=hits[: payload.limit],
        )


def _tokens(value: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in _TOKEN_RE.findall(value.lower()):
        if len(match) < 2 or match in seen:
            continue
        seen.add(match)
        result.append(match)
    return result


def _snippet(body: str, tokens: list[str], *, width: int = 520) -> str:
    normalized = " ".join(body.split())
    lowered = normalized.lower()
    positions = [lowered.find(token.lower()) for token in tokens]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - 100)
    end = min(len(normalized), start + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end]}{suffix}"


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cluster_name(papers: list[Paper]) -> tuple[str, list[str]]:
    stop = {
        "with",
        "from",
        "using",
        "based",
        "towards",
        "method",
        "model",
        "learning",
        "analysis",
        "study",
        "for",
        "the",
        "and",
        "into",
        "under",
    }
    counts = Counter(
        token
        for paper in papers
        for token in _tokens(paper.title)
        if token not in stop and len(token) > 2
    )
    keywords = [token for token, _ in counts.most_common(12)]
    if keywords:
        return " · ".join(keywords[:3]), keywords
    fallback = papers[0].primary_category or papers[0].venue or papers[0].source or "Other"
    return fallback, [fallback]


async def record_card_version(
    db: AsyncSession,
    card: ReadingCard,
    *,
    actor_id: uuid.UUID,
    source_type: str,
    source_run_id: uuid.UUID | None,
) -> ReadingCardVersion:
    await db.flush()
    version = ReadingCardVersion(
        project_id=card.project_id,
        mission_id=card.mission_id,
        paper_id=card.paper_id,
        card_id=card.id,
        version=card.version,
        snapshot_json={
            "summary": card.summary,
            "research_question": card.research_question,
            "method_flow": card.method_flow_json,
            "strengths": card.strengths_json,
            "limitations": card.limitations_json,
            "reproducibility": card.reproducibility_json,
            "claims": card.claims_json,
            "status": card.status,
        },
        source_type=source_type,
        source_run_id=source_run_id,
        created_by=actor_id,
    )
    db.add(version)
    await db.flush()
    return version
