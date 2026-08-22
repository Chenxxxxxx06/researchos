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
from researchos.research.models import Idea, Paper, PaperSection

from .embeddings import embed_texts, hashing_embedding
from .indexing import (
    ensure_project_chunks,
    ensure_project_tuples,
    index_reading_card_tuples,
)
from .models import (
    MissionPaper,
    MissionTopicCluster,
    PaperChunk,
    PaperKnowledgeTuple,
    ReadingCard,
    ReadingCardVersion,
    ReadingNote,
)
from .profiles import get_active_profile
from .schemas import (
    AddMissionPapersRequest,
    BenchmarkRecommendation,
    DirectionRecommendation,
    MissionPaperResponse,
    RagHitResponse,
    RagSearchRequest,
    RagSearchResponse,
    ReadingCardUpsertRequest,
    ReadingNoteCreateRequest,
    ReadingNoteUpdateRequest,
    ResearchSynthesisResponse,
    UpdateTopicClusterRequest,
)

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff-]+", re.UNICODE)
# Hybrid retrieval (§7.3): per-leg recall depth, RRF constant, diversity cap.
_RECALL_PER_LEG = 40
_RRF_K = 60
MAX_HITS_PER_PAPER = 3


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
        card.reading_focus_json = [kind.value for kind in payload.reading_focus]
        card.method_flow_json = payload.method_flow
        card.experimental_setup_json = payload.experimental_setup
        card.key_results_json = payload.key_results
        card.conclusions_json = payload.conclusions
        card.strengths_json = payload.strengths
        card.limitations_json = payload.limitations
        card.reproducibility_json = payload.reproducibility
        card.github_repositories_json = payload.github_repositories
        card.paper_ideas_json = payload.paper_ideas
        card.benchmarks_json = payload.benchmarks
        card.ablation_findings_json = payload.ablation_findings
        card.knowledge_tuples_json = payload.knowledge_tuples
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
        await index_reading_card_tuples(self.db, card)
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

    async def research_synthesis(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
    ) -> ResearchSynthesisResponse:
        """Rank the top ten directions and strongest benchmarks from cards.

        The score is deterministic and evidence-oriented. It deliberately
        favors cross-paper support, explicit benchmark protocols, reported
        ablations, and available code over rhetorical novelty.
        """

        await self._mission(actor, project_id, mission_id, write=False)
        rows = (
            await self.db.execute(
                select(ReadingCard, Paper)
                .join(Paper, Paper.id == ReadingCard.paper_id)
                .where(ReadingCard.mission_id == mission_id)
                .order_by(Paper.published_at.desc().nullslast(), Paper.title.asc())
            )
        ).all()
        tuple_count = int(
            await self.db.scalar(
                select(func.count())
                .select_from(PaperKnowledgeTuple)
                .where(PaperKnowledgeTuple.mission_id == mission_id)
            )
            or 0
        )
        card_rows = [(card, paper) for card, paper in rows]
        directions = _rank_directions(card_rows)
        benchmarks = _rank_benchmarks(card_rows)
        return ResearchSynthesisResponse(
            mission_id=mission_id,
            paper_count=len(rows),
            reviewed_card_count=sum(card.status == "reviewed" for card, _ in rows),
            tuple_count=tuple_count,
            directions=directions,
            benchmarks=benchmarks,
            generated_at=datetime.now(tz=UTC),
        )

    async def materialize_directions(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
    ) -> ResearchSynthesisResponse:
        await self._mission(actor, project_id, mission_id, write=True)
        synthesis = await self.research_synthesis(actor, project_id, mission_id)
        existing = list(
            (await self.db.execute(select(Idea).where(Idea.project_id == project_id)))
            .scalars()
            .all()
        )
        by_key = {
            str((idea.metadata_json or {}).get("recommendation_key")): idea
            for idea in existing
            if (idea.metadata_json or {}).get("mission_id") == str(mission_id)
        }
        for item in synthesis.directions:
            key = _normal_key(item.title)
            idea = by_key.get(key)
            metadata = {
                "source": "paper-insight-ranking-v1",
                "mission_id": str(mission_id),
                "recommendation_key": key,
                "rank": item.rank,
                "score": item.score,
                "score_components": item.score_components,
                "source_paper_ids": [str(value) for value in item.source_paper_ids],
                "benchmarks": item.benchmarks,
                "ablation_signals": item.ablation_signals,
                "code_repositories": item.code_repositories,
                "evidence_status": item.evidence_status,
            }
            if idea is None:
                self.db.add(
                    Idea(
                        project_id=project_id,
                        title=item.title,
                        description=item.rationale,
                        hypothesis=item.hypothesis,
                        novelty_score=item.score,
                        metadata_json=metadata,
                        created_by=actor.id,
                    )
                )
            else:
                idea.description = item.rationale
                idea.hypothesis = item.hypothesis
                idea.novelty_score = item.score
                idea.metadata_json = metadata
        await self.db.commit()
        return synthesis

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
        await ensure_project_tuples(self.db, project_id)
        profile = get_active_profile()
        query_vector = (await embed_texts([payload.query], profile))[0]

        distance = PaperChunk.embedding.cosine_distance(query_vector)
        # Keyword leg: ts_rank (not ts_rank_cd — cover density scores natural
        # multi-term queries 0) over an OR tsquery built from the extracted
        # tokens. Measured on PG16: even ts_rank floors at 1e-20 for AND
        # tsqueries when fewer than two lexemes match, so AND semantics would
        # keep partial matches scoreless; the OR form gives every overlap
        # credit and ranks multi-token matches higher naturally. Tokens come
        # from _tokens (regex-sanitized), so single-quoting them is safe.
        ts_query = func.to_tsquery("simple", " | ".join(f"'{token}'" for token in tokens))
        keyword_rank = func.ts_rank(PaperChunk.search_tsv, ts_query)

        def _filtered(statement):  # identical candidate pool for both legs
            statement = statement.join(Paper, Paper.id == PaperChunk.paper_id).where(
                PaperChunk.project_id == project_id
            )
            if payload.mission_id is not None:
                statement = statement.join(
                    MissionPaper, MissionPaper.paper_id == PaperChunk.paper_id
                ).where(MissionPaper.mission_id == payload.mission_id)
            if payload.kinds:
                statement = statement.where(
                    PaperChunk.section_kind.in_([kind.value for kind in payload.kinds])
                )
            return statement

        vector_rows = (
            await self.db.execute(
                _filtered(select(PaperChunk, Paper, distance.label("vector_distance")))
                .order_by(distance.asc(), PaperChunk.id.asc())
                .limit(_RECALL_PER_LEG)
            )
        ).all()
        keyword_rows = (
            await self.db.execute(
                _filtered(select(PaperChunk, Paper, keyword_rank.label("keyword_rank")))
                # ts_rank returns a 1e-20 floor for documents sharing no
                # lexeme with the query; real (partial) matches score orders
                # of magnitude higher, so the threshold admits partial matches
                # while keeping true non-matches out of the keyword leg.
                .where(keyword_rank > 1e-10)
                .order_by(keyword_rank.desc(), PaperChunk.id.asc())
                .limit(_RECALL_PER_LEG)
            )
        ).all()

        tuple_distance = PaperKnowledgeTuple.embedding.cosine_distance(query_vector)
        tuple_keyword_rank = func.ts_rank(PaperKnowledgeTuple.search_tsv, ts_query)

        def _filtered_tuples(statement):
            statement = statement.join(Paper, Paper.id == PaperKnowledgeTuple.paper_id).where(
                PaperKnowledgeTuple.project_id == project_id,
                PaperKnowledgeTuple.embedding_model == profile.name,
            )
            if payload.mission_id is not None:
                statement = statement.where(PaperKnowledgeTuple.mission_id == payload.mission_id)
            if payload.kinds:
                statement = statement.join(
                    PaperSection, PaperSection.id == PaperKnowledgeTuple.section_id
                ).where(PaperSection.kind.in_(payload.kinds))
            return statement

        tuple_vector_rows = (
            await self.db.execute(
                _filtered_tuples(
                    select(
                        PaperKnowledgeTuple,
                        Paper,
                        tuple_distance.label("vector_distance"),
                    )
                )
                .order_by(tuple_distance.asc(), PaperKnowledgeTuple.id.asc())
                .limit(_RECALL_PER_LEG)
            )
        ).all()
        tuple_keyword_rows = (
            await self.db.execute(
                _filtered_tuples(
                    select(
                        PaperKnowledgeTuple,
                        Paper,
                        tuple_keyword_rank.label("keyword_rank"),
                    )
                )
                .where(tuple_keyword_rank > 1e-10)
                .order_by(tuple_keyword_rank.desc(), PaperKnowledgeTuple.id.asc())
                .limit(_RECALL_PER_LEG)
            )
        ).all()

        candidates: dict[str, tuple[PaperChunk | PaperKnowledgeTuple, Paper]] = {}
        vector_leg: dict[str, float] = {}
        keyword_leg: dict[str, float] = {}
        for chunk, paper, raw_distance in vector_rows:
            key = f"chunk:{chunk.id}"
            candidates[key] = (chunk, paper)
            vector_leg[key] = max(-1.0, min(1.0, 1.0 - float(raw_distance or 0.0)))
        for chunk, paper, raw_rank in keyword_rows:
            key = f"chunk:{chunk.id}"
            candidates[key] = (chunk, paper)
            keyword_leg[key] = max(0.0, min(1.0, float(raw_rank or 0.0)))
        for item, paper, raw_distance in tuple_vector_rows:
            key = f"tuple:{item.id}"
            candidates[key] = (item, paper)
            vector_leg[key] = max(-1.0, min(1.0, 1.0 - float(raw_distance or 0.0)))
        for item, paper, raw_rank in tuple_keyword_rows:
            key = f"tuple:{item.id}"
            candidates[key] = (item, paper)
            keyword_leg[key] = max(0.0, min(1.0, float(raw_rank or 0.0)))

        rrf_scores = _rrf_fuse(list(vector_leg), list(keyword_leg))
        ordered = sorted(rrf_scores, key=lambda key: (-rrf_scores[key], key))

        # Diversity: at most MAX_HITS_PER_PAPER snippets/tuples per paper; if
        # that cannot fill the requested limit, top up from the remainder.
        selected: list[str] = []
        per_paper: Counter[uuid.UUID] = Counter()
        for key in ordered:
            paper_id = candidates[key][0].paper_id
            if per_paper[paper_id] < MAX_HITS_PER_PAPER:
                per_paper[paper_id] += 1
                selected.append(key)
                if len(selected) >= payload.limit:
                    break
        if len(selected) < payload.limit:
            for key in ordered:
                if key not in selected:
                    selected.append(key)
                    if len(selected) >= payload.limit:
                        break

        hits: list[RagHitResponse] = []
        for key in selected:
            candidate, paper = candidates[key]
            reasons: list[str] = []
            if key in vector_leg:
                reasons.append("vector")
            if key in keyword_leg:
                reasons.append("keyword")
            if isinstance(candidate, PaperKnowledgeTuple):
                reasons.append("knowledge_tuple")
                hits.append(
                    RagHitResponse(
                        tuple_id=candidate.id,
                        tuple_kind=candidate.tuple_kind,
                        is_inference=candidate.is_inference,
                        evidence_status=candidate.evidence_status,
                        paper_id=paper.id,
                        section_id=candidate.section_id,
                        title=paper.title,
                        heading=f"Tuple · {candidate.tuple_kind}",
                        kind=None,
                        snippet=_snippet(candidate.content, tokens),
                        score=round(rrf_scores[key], 4),
                        vector_score=round(vector_leg.get(key, 0.0), 4),
                        keyword_score=round(keyword_leg.get(key, 0.0), 4),
                        match_reasons=reasons,
                        citation_key=f"{paper.source}:{paper.external_id}",
                    )
                )
            else:
                hits.append(
                    RagHitResponse(
                        chunk_id=candidate.id,
                        paper_id=paper.id,
                        section_id=candidate.section_id,
                        title=paper.title,
                        heading=candidate.heading,
                        kind=candidate.section_kind,
                        snippet=_snippet(candidate.content, tokens),
                        score=round(rrf_scores[key], 4),
                        vector_score=round(vector_leg.get(key, 0.0), 4),
                        keyword_score=round(keyword_leg.get(key, 0.0), 4),
                        match_reasons=reasons,
                        char_start=candidate.char_start,
                        char_end=candidate.char_end,
                        citation_key=f"{paper.source}:{paper.external_id}",
                    )
                )
        indexed_tuples = int(
            await self.db.scalar(
                select(func.count())
                .select_from(PaperKnowledgeTuple)
                .where(PaperKnowledgeTuple.project_id == project_id)
            )
            or 0
        )
        return RagSearchResponse(
            query=payload.query,
            mode="hybrid-vector-keyword-tuples-v3",
            embedding_model=profile.name,
            indexed_papers=indexed_papers,
            indexed_chunks=indexed_chunks,
            indexed_tuples=indexed_tuples,
            hits=hits,
        )


def _rrf_fuse(
    vector_ids: list[str], keyword_ids: list[str], *, k: int = _RRF_K
) -> dict[str, float]:
    """Reciprocal Rank Fusion: ``score = Σ 1/(k + rank)`` over both legs."""

    scores: dict[str, float] = {}
    for ids in (vector_ids, keyword_ids):
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


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


def _normal_key(value: str) -> str:
    return " ".join(_tokens(value))[:240]


def _item_text(item: dict, *keys: str) -> str:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _rank_directions(rows: list[tuple[ReadingCard, Paper]]) -> list[DirectionRecommendation]:
    grouped: dict[str, dict] = {}
    for card, paper in rows:
        ideas = [item for item in (card.paper_ideas_json or []) if isinstance(item, dict)]
        if not ideas:
            ideas = [
                {
                    "title": f"Address limitation: {str(limit)[:180]}",
                    "hypothesis": "Resolving this reported limitation improves robustness.",
                    "motivation": str(limit),
                    "inference": True,
                    "evidence_status": "needs_evidence",
                }
                for limit in (card.limitations_json or [])[:5]
                if str(limit).strip()
            ]
        benchmark_names = [
            _item_text(item, "name", "dataset", "task")
            for item in (card.benchmarks_json or [])
            if isinstance(item, dict)
        ]
        ablations = [
            _item_text(item, "component", "comparison", "effect")
            for item in (card.ablation_findings_json or [])
            if isinstance(item, dict)
        ]
        repositories = [
            _item_text(item, "url")
            for item in (card.github_repositories_json or [])
            if isinstance(item, dict)
        ]
        for raw in ideas:
            title = _item_text(raw, "title", "idea", "head")[:300]
            if not title:
                continue
            key = _normal_key(title)
            if not key:
                continue
            entry = grouped.setdefault(
                key,
                {
                    "title": title,
                    "hypothesis": _item_text(raw, "hypothesis", "tail"),
                    "rationales": [],
                    "papers": set(),
                    "grounded": 0,
                    "reported_unreviewed": 0,
                    "reviewed": 0,
                    "benchmarks": set(),
                    "ablations": set(),
                    "repositories": set(),
                },
            )
            entry["papers"].add(paper.id)
            is_reported = raw.get("evidence_status") == "reported"
            entry["grounded"] += int(is_reported and card.status == "reviewed")
            entry["reported_unreviewed"] += int(is_reported and card.status != "reviewed")
            entry["reviewed"] += int(card.status == "reviewed")
            rationale = _item_text(raw, "motivation", "rationale", "description")
            if rationale:
                entry["rationales"].append(rationale)
            entry["benchmarks"].update(value for value in benchmark_names if value)
            entry["ablations"].update(value for value in ablations if value)
            entry["repositories"].update(value for value in repositories if value)

    scored: list[tuple[float, str, dict, dict[str, float]]] = []
    for key, entry in grouped.items():
        paper_count = len(entry["papers"])
        components = {
            "evidence": min(1.0, entry["grounded"] / max(1, paper_count)),
            "cross_paper": min(1.0, paper_count / 3),
            "benchmark_coverage": min(1.0, len(entry["benchmarks"]) / 3),
            "ablation_support": min(1.0, len(entry["ablations"]) / 2),
            "code_availability": 1.0 if entry["repositories"] else 0.0,
            "human_review": min(1.0, entry["reviewed"] / max(1, paper_count)),
        }
        score = (
            0.30 * components["evidence"]
            + 0.20 * components["cross_paper"]
            + 0.20 * components["benchmark_coverage"]
            + 0.15 * components["ablation_support"]
            + 0.10 * components["code_availability"]
            + 0.05 * components["human_review"]
        )
        scored.append((score, key, entry, components))
    scored.sort(key=lambda row: (-row[0], row[1]))

    result: list[DirectionRecommendation] = []
    for rank, (score, _key, entry, components) in enumerate(scored[:10], start=1):
        rationales = list(dict.fromkeys(entry["rationales"]))
        rationale = " ".join(rationales[:3]).strip() or (
            "Derived from structured limitations and experiment evidence; validate before use."
        )
        result.append(
            DirectionRecommendation(
                rank=rank,
                title=entry["title"],
                hypothesis=entry["hypothesis"] or "A falsifiable hypothesis is not yet reported.",
                rationale=rationale[:2000],
                score=round(score, 4),
                score_components={key: round(value, 4) for key, value in components.items()},
                source_paper_ids=sorted(entry["papers"], key=str),
                benchmarks=sorted(entry["benchmarks"])[:20],
                ablation_signals=sorted(entry["ablations"])[:20],
                code_repositories=sorted(entry["repositories"])[:20],
                evidence_status=(
                    "reported"
                    if entry["grounded"]
                    else "provisional"
                    if entry["reported_unreviewed"]
                    else "inferred"
                ),
            )
        )
    return result


def _rank_benchmarks(rows: list[tuple[ReadingCard, Paper]]) -> list[BenchmarkRecommendation]:
    grouped: dict[str, dict] = {}
    for card, paper in rows:
        has_code = any(
            isinstance(item, dict) and bool(_item_text(item, "url"))
            for item in (card.github_repositories_json or [])
        )
        has_ablation = bool(card.ablation_findings_json)
        for raw in card.benchmarks_json or []:
            if not isinstance(raw, dict):
                continue
            name = _item_text(raw, "name", "dataset", "task")[:300]
            if not name:
                continue
            key = _normal_key(name)
            entry = grouped.setdefault(
                key,
                {
                    "name": name,
                    "task": _item_text(raw, "task"),
                    "papers": set(),
                    "metrics": set(),
                    "splits": set(),
                    "grounded": 0,
                    "code": False,
                    "ablation": False,
                },
            )
            entry["papers"].add(paper.id)
            metric = _item_text(raw, "metric", "metrics")
            split = _item_text(raw, "split", "data_split", "protocol")
            if metric:
                entry["metrics"].add(metric)
            if split:
                entry["splits"].add(split)
            entry["grounded"] += int(
                raw.get("evidence_status") == "reported" and card.status == "reviewed"
            )
            entry["code"] = entry["code"] or has_code
            entry["ablation"] = entry["ablation"] or has_ablation

    scored: list[tuple[float, str, dict, list[str]]] = []
    for key, entry in grouped.items():
        paper_count = len(entry["papers"])
        support = min(1.0, paper_count / 4)
        grounded = min(1.0, entry["grounded"] / max(1, paper_count))
        protocol = 0.5 * bool(entry["metrics"]) + 0.5 * bool(entry["splits"])
        score = (
            0.35 * support
            + 0.30 * grounded
            + 0.20 * protocol
            + 0.075 * bool(entry["code"])
            + 0.075 * bool(entry["ablation"])
        )
        reasons = [f"reported by {paper_count} paper(s)"]
        if entry["metrics"]:
            reasons.append("explicit evaluation metric")
        if entry["splits"]:
            reasons.append("explicit split or protocol")
        if entry["code"]:
            reasons.append("code link available")
        if entry["ablation"]:
            reasons.append("supports ablation analysis")
        scored.append((score, key, entry, reasons))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        BenchmarkRecommendation(
            rank=rank,
            name=entry["name"],
            task=entry["task"] or "Task not explicitly reported",
            metrics=sorted(entry["metrics"])[:20],
            splits=sorted(entry["splits"])[:20],
            source_paper_ids=sorted(entry["papers"], key=str),
            paper_count=len(entry["papers"]),
            credibility_score=round(score, 4),
            reasons=reasons,
        )
        for rank, (score, _key, entry, reasons) in enumerate(scored[:8], start=1)
    ]


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
            "reading_focus": card.reading_focus_json,
            "method_flow": card.method_flow_json,
            "experimental_setup": card.experimental_setup_json,
            "key_results": card.key_results_json,
            "conclusions": card.conclusions_json,
            "strengths": card.strengths_json,
            "limitations": card.limitations_json,
            "reproducibility": card.reproducibility_json,
            "github_repositories": card.github_repositories_json,
            "paper_ideas": card.paper_ideas_json,
            "benchmarks": card.benchmarks_json,
            "ablation_findings": card.ablation_findings_json,
            "knowledge_tuples": card.knowledge_tuples_json,
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
