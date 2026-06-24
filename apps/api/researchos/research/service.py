"""Research business logic and authorization.

Permission checks (project access, tenant isolation) live here via
``ProjectService.ensure_access``.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError
from researchos.common.pagination import Page
from researchos.common.rate_limit import enforce_rate_limit
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.research.providers import PaperResult, get_paper_provider

from .enums import IdeaStatus
from .models import Idea, Paper, ResearchCritique
from .repository import CritiqueRepository, IdeaRepository, PaperRepository


class PaperService:
    def __init__(self, db: AsyncSession, *, http_client: httpx.AsyncClient | None = None) -> None:
        self.db = db
        self.papers = PaperRepository(db)
        self.projects = ProjectService(db)
        self._http_client = http_client

    async def search(
        self, actor: User, project_id: uuid.UUID, *, query: str, limit: int
    ) -> list[PaperResult]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        settings = get_settings()
        await enforce_rate_limit(
            f"paper_search:{actor.id}",
            limit=settings.rate_limit_paper_search_per_minute,
        )
        provider = get_paper_provider(client=self._http_client)
        capped = min(limit, settings.paper_search_max_results)
        return await provider.search(query, limit=capped)

    async def import_papers(
        self, actor: User, project_id: uuid.UUID, results: list[PaperResult]
    ) -> list[Paper]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        imported: list[Paper] = []
        for result in results:
            existing = await self.papers.get_by_external(
                project_id, result.source, result.external_id
            )
            if existing is not None:
                imported.append(existing)
                continue
            paper = await self.papers.create(
                Paper(
                    project_id=project_id,
                    source=result.source,
                    external_id=result.external_id,
                    title=result.title,
                    abstract=result.abstract,
                    authors_json=result.authors,
                    venue=result.venue,
                    published_at=result.published_at,
                    url=result.url,
                    pdf_url=result.pdf_url,
                    metadata_json=result.extra,
                    imported_by=actor.id,
                )
            )
            imported.append(paper)
        await self.db.commit()
        return imported

    async def list_library(
        self, actor: User, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[Paper]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        items, total = await self.papers.list_by_project(project_id, limit=limit, offset=offset)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get(self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID) -> Paper:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        return paper

    async def delete(self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        await self.papers.delete(paper)
        await self.db.commit()


class IdeaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ideas = IdeaRepository(db)
        self.projects = ProjectService(db)

    async def create(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        title: str,
        description: str,
        hypothesis: str | None,
    ) -> Idea:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        idea = await self.ideas.create(
            Idea(
                project_id=project_id,
                title=title,
                description=description,
                hypothesis=hypothesis,
                created_by=actor.id,
            )
        )
        await self.db.commit()
        await self.db.refresh(idea)
        return idea

    async def list(
        self, actor: User, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[Idea]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        items, total = await self.ideas.list_by_project(project_id, limit=limit, offset=offset)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get(self, actor: User, project_id: uuid.UUID, idea_id: uuid.UUID) -> Idea:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        idea = await self.ideas.get_by_id(project_id, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found.")
        return idea

    async def update(
        self,
        actor: User,
        project_id: uuid.UUID,
        idea_id: uuid.UUID,
        *,
        title: str | None,
        description: str | None,
        hypothesis: str | None,
        status: IdeaStatus | None,
    ) -> Idea:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        idea = await self.ideas.get_by_id(project_id, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found.")
        if title is not None:
            idea.title = title
        if description is not None:
            idea.description = description
        if hypothesis is not None:
            idea.hypothesis = hypothesis
        if status is not None:
            idea.status = status
        await self.db.commit()
        await self.db.refresh(idea)
        return idea


class CritiqueService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.critiques = CritiqueRepository(db)
        self.projects = ProjectService(db)

    async def list_for_idea(
        self, actor: User, project_id: uuid.UUID, idea_id: uuid.UUID
    ) -> list[ResearchCritique]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.critiques.list_by_idea(project_id, idea_id)
