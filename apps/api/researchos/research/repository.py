"""Research data access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Idea, Paper, ResearchCritique


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

    async def create(self, paper: Paper) -> Paper:
        self.db.add(paper)
        await self.db.flush()
        return paper

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

    async def list_ids_for_project(self, project_id: uuid.UUID) -> set[str]:
        """Return the set of citation keys (``source:external_id``) in the library."""

        result = await self.db.execute(
            select(Paper.source, Paper.external_id).where(Paper.project_id == project_id)
        )
        return {f"{s}:{e}" for s, e in result.all()}

    async def delete(self, paper: Paper) -> None:
        await self.db.delete(paper)
        await self.db.flush()


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
