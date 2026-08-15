"""Research data access."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.experiment_plans.models import ExperimentPlan
from researchos.knowledge.models import MissionPaper, ReadingCard, ReadingNote
from researchos.reviews.models import ReviewSection

from .enums import PaperSectionKind
from .models import Idea, Paper, PaperSection, ResearchCritique, ResearchFeedPref


class PaperRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, project_id: uuid.UUID, paper_id: uuid.UUID) -> Paper | None:
        paper = await self.db.get(Paper, paper_id)
        if paper is None or paper.project_id != project_id:
            return None
        return paper

    async def get_by_external(
        self, project_id: uuid.UUID, source: str, external_id: str
    ) -> Paper | None:
        result = await self.db.execute(
            select(Paper).where(
                Paper.project_id == project_id,
                Paper.source == source,
                Paper.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_existing_keys(
        self, project_id: uuid.UUID, keys: list[tuple[str, str]]
    ) -> list[Paper]:
        """Rows matching any ``(source, external_id)`` pair, in one query."""

        if not keys:
            return []
        result = await self.db.execute(
            select(Paper).where(
                Paper.project_id == project_id,
                tuple_(Paper.source, Paper.external_id).in_(keys),
            )
        )
        return list(result.scalars().all())

    async def find_by_dois_or_arxiv_ids(
        self, project_id: uuid.UUID, *, dois: list[str], arxiv_ids: list[str]
    ) -> list[Paper]:
        """Cross-source duplicate lookup by DOI / arXiv id columns."""

        clauses = []
        if dois:
            clauses.append(Paper.doi.in_(dois))
        if arxiv_ids:
            clauses.append(Paper.arxiv_id.in_(arxiv_ids))
        if not clauses:
            return []
        result = await self.db.execute(
            select(Paper).where(Paper.project_id == project_id, or_(*clauses))
        )
        return list(result.scalars().all())

    async def create(self, paper: Paper) -> Paper:
        self.db.add(paper)
        await self.db.flush()
        return paper

    async def add_all(self, papers: list[Paper]) -> None:
        self.db.add_all(papers)
        await self.db.flush()

    async def list_by_project(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Paper], int]:
        total = await self.db.scalar(
            select(func.count()).select_from(Paper).where(Paper.project_id == project_id)
        )
        result = await self.db.execute(
            select(Paper)
            .where(Paper.project_id == project_id)
            .order_by(Paper.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_recent(self, project_id: uuid.UUID, *, limit: int) -> list[Paper]:
        result = await self.db.execute(
            select(Paper)
            .where(Paper.project_id == project_id)
            .order_by(Paper.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_library_docs(self, project_id: uuid.UUID, *, limit: int = 500) -> list[str]:
        """Newest library docs as ``title + " " + abstract`` strings (ranking)."""

        result = await self.db.execute(
            select(Paper.title, Paper.abstract)
            .where(Paper.project_id == project_id)
            .order_by(Paper.created_at.desc())
            .limit(limit)
        )
        return [f"{title} {abstract or ''}".strip() for title, abstract in result.all()]

    async def list_ids_for_project(self, project_id: uuid.UUID) -> set[str]:
        """Return the set of citation keys (``source:external_id``) in the library."""

        result = await self.db.execute(
            select(Paper.source, Paper.external_id).where(Paper.project_id == project_id)
        )
        return {f"{s}:{e}" for s, e in result.all()}

    async def count_by_primary_category(
        self, project_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        """Non-null primary categories with counts, most frequent first."""

        result = await self.db.execute(
            select(Paper.primary_category, func.count())
            .where(Paper.project_id == project_id, Paper.primary_category.is_not(None))
            .group_by(Paper.primary_category)
            .order_by(func.count().desc(), Paper.primary_category.asc())
        )
        return [(category, int(count)) for category, count in result.all()]

    async def delete(self, paper: Paper) -> None:
        await self.db.delete(paper)
        await self.db.flush()

    async def reference_counts(
        self, project_id: uuid.UUID, paper_id: uuid.UUID
    ) -> dict[str, int]:
        """Count downstream artifacts referencing a paper (delete preflight).

        Reading cards/notes and mission links carry a direct ``paper_id`` FK.
        Review sections cite papers via ``citations_json`` (list of paper-id
        strings) and grounded ``claims_json`` entries; experiment plans via
        ``baselines_json[*].source_paper_id`` — both queried with JSONB
        containment against the real stored shapes.
        """

        pid = str(paper_id)

        async def _count(model, *clauses) -> int:  # noqa: ANN001, ANN202 - local helper
            stmt = (
                select(func.count())
                .select_from(model)
                .where(model.project_id == project_id, *clauses)
            )
            return int(await self.db.scalar(stmt) or 0)

        return {
            "reading_cards": await _count(ReadingCard, ReadingCard.paper_id == paper_id),
            "reading_notes": await _count(ReadingNote, ReadingNote.paper_id == paper_id),
            "review_sections": await _count(
                ReviewSection,
                or_(
                    ReviewSection.citations_json.contains([pid]),
                    ReviewSection.claims_json.contains([{"paper_id": pid}]),
                ),
            ),
            "experiment_plans": await _count(
                ExperimentPlan,
                ExperimentPlan.baselines_json.contains([{"source_paper_id": pid}]),
            ),
            "missions": await _count(MissionPaper, MissionPaper.paper_id == paper_id),
        }


class PaperSectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def replace_for_paper(
        self, paper_id: uuid.UUID, sections: list[PaperSection]
    ) -> None:
        """Idempotent full replace (safe under acks_late task redelivery)."""

        await self.db.execute(delete(PaperSection).where(PaperSection.paper_id == paper_id))
        self.db.add_all(sections)
        await self.db.flush()

    async def list_by_paper(self, paper_id: uuid.UUID) -> list[PaperSection]:
        result = await self.db.execute(
            select(PaperSection)
            .where(PaperSection.paper_id == paper_id)
            .order_by(PaperSection.seq.asc())
        )
        return list(result.scalars().all())

    async def list_for_papers_by_kind(
        self, paper_ids: list[uuid.UUID], kind: PaperSectionKind
    ) -> list[PaperSection]:
        if not paper_ids:
            return []
        result = await self.db.execute(
            select(PaperSection)
            .where(PaperSection.paper_id.in_(paper_ids), PaperSection.kind == kind)
            .order_by(PaperSection.paper_id, PaperSection.seq.asc())
        )
        return list(result.scalars().all())


class FeedPrefRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, project_id: uuid.UUID) -> ResearchFeedPref | None:
        return await self.db.get(ResearchFeedPref, project_id)

    async def upsert(self, project_id: uuid.UUID, categories: list[str]) -> ResearchFeedPref:
        pref = await self.db.get(ResearchFeedPref, project_id)
        if pref is None:
            pref = ResearchFeedPref(project_id=project_id, categories=categories)
            self.db.add(pref)
        else:
            pref.categories = categories
        await self.db.flush()
        return pref


class IdeaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, project_id: uuid.UUID, idea_id: uuid.UUID) -> Idea | None:
        idea = await self.db.get(Idea, idea_id)
        if idea is None or idea.project_id != project_id:
            return None
        return idea

    async def create(self, idea: Idea) -> Idea:
        self.db.add(idea)
        await self.db.flush()
        return idea

    async def list_by_project(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Idea], int]:
        total = await self.db.scalar(
            select(func.count()).select_from(Idea).where(Idea.project_id == project_id)
        )
        result = await self.db.execute(
            select(Idea)
            .where(Idea.project_id == project_id)
            .order_by(Idea.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)


class CritiqueRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, critique: ResearchCritique) -> ResearchCritique:
        self.db.add(critique)
        await self.db.flush()
        return critique

    async def list_by_idea(
        self, project_id: uuid.UUID, idea_id: uuid.UUID
    ) -> list[ResearchCritique]:
        result = await self.db.execute(
            select(ResearchCritique)
            .where(
                ResearchCritique.project_id == project_id,
                ResearchCritique.idea_id == idea_id,
            )
            .order_by(ResearchCritique.created_at.desc())
        )
        return list(result.scalars().all())
