"""Research business logic and authorization.

Permission checks (project access, tenant isolation) live here via
``ProjectService.ensure_access``. Paper import is server-verified: metadata is
re-fetched from providers by ``(source, external_id)`` so clients can never
fabricate library entries (which would poison the citation whitelist).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.celery_app import get_celery_client
from researchos.common.config import get_settings
from researchos.common.errors import AppError, NotFoundError, ValidationError
from researchos.common.pagination import Page
from researchos.common.rate_limit import enforce_rate_limit
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.models import Project
from researchos.projects.service import ProjectService
from researchos.research.providers import (
    PROVIDER_NAMES,
    FederatedProvider,
    PaperImportRef,
    PaperResult,
    PaperSearchFilters,
    get_paper_provider,
    get_provider_by_name,
)
from researchos.research.providers.federated import normalize_arxiv_id, normalize_doi

from .enums import IdeaStatus, PaperIngestStatus, PaperSectionKind
from .models import Idea, Paper, PaperSection, ResearchCritique
from .ranking import rank_results
from .repository import (
    CritiqueRepository,
    IdeaRepository,
    PaperRepository,
    PaperSectionRepository,
)
from .schemas import SkippedImport

logger = structlog.get_logger(__name__)

INGEST_TASK = "ingestion.paper_fulltext"
_AGENT_SECTION_BODY_MAX = 2_000


def _dispatch_ingest(paper_id: uuid.UUID) -> None:
    """Best-effort Celery dispatch; a down broker never fails the request."""

    try:
        get_celery_client().send_task(INGEST_TASK, args=[str(paper_id)], queue="ingestion")
    except Exception as exc:  # noqa: BLE001 - broker outages degrade gracefully
        logger.warning("ingest_dispatch_failed", paper_id=str(paper_id), error=str(exc))


class IngestRunningError(AppError):
    code = "ingest_running"
    http_status = 409
    message = "Ingestion is already running for this paper."


class PaperHasReferencesError(AppError):
    code = "paper_has_references"
    http_status = 409
    message = "Paper is still referenced by project artifacts."


class PaperService:
    def __init__(self, db: AsyncSession, *, http_client: httpx.AsyncClient | None = None) -> None:
        self.db = db
        self.papers = PaperRepository(db)
        self.sections = PaperSectionRepository(db)
        self.projects = ProjectService(db)
        self._http_client = http_client

    # --- search --------------------------------------------------------------
    async def search_with_status(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        query: str,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> tuple[list[PaperResult], dict[str, str]]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        settings = get_settings()
        await enforce_rate_limit(
            f"paper_search:{actor.id}",
            limit=settings.rate_limit_paper_search_per_minute,
        )
        provider = get_paper_provider(client=self._http_client)
        capped = min(limit, settings.paper_search_max_results)
        results = await provider.search(query, limit=capped, filters=filters)
        if isinstance(provider, FederatedProvider):
            provider_status = dict(provider.last_status)
        else:
            provider_status = {provider.name: "ok"}

        sort = filters.sort if filters is not None else "relevance"
        if sort == "latest":
            results.sort(
                key=lambda r: (
                    r.published_at is None,
                    -(r.published_at.timestamp() if r.published_at else 0.0),
                )
            )
        else:
            docs = await self.papers.list_library_docs(project_id, limit=500)
            results = rank_results(results, library_docs=docs)
        return results, provider_status

    async def search(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        query: str,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]:
        """Back-compat wrapper (agent tools consume the bare result list)."""

        results, _ = await self.search_with_status(
            actor, project_id, query=query, limit=limit, filters=filters
        )
        return results

    # --- verified import ------------------------------------------------------
    async def import_papers(
        self, actor: User, project_id: uuid.UUID, refs: Sequence[PaperImportRef]
    ) -> tuple[list[Paper], list[SkippedImport]]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)

        # De-duplicate the request while preserving order.
        ordered_refs: list[PaperImportRef] = []
        seen_refs: set[tuple[str, str]] = set()
        for ref in refs:
            key = (ref.source, ref.external_id)
            if key not in seen_refs:
                seen_refs.add(key)
                ordered_refs.append(ref)

        skipped: list[SkippedImport] = []
        fetched: dict[tuple[str, str], PaperResult] = {}

        by_source: dict[str, list[PaperImportRef]] = {}
        for ref in ordered_refs:
            by_source.setdefault(ref.source, []).append(ref)

        for source, source_refs in by_source.items():
            if source not in PROVIDER_NAMES:
                skipped.extend(
                    SkippedImport(
                        source=source, external_id=ref.external_id, reason="invalid_source"
                    )
                    for ref in source_refs
                )
                continue
            provider = get_provider_by_name(source, client=self._http_client)
            try:
                results = await provider.fetch_by_ids([r.external_id for r in source_refs])
            except Exception as exc:  # noqa: BLE001 - partial success is preserved
                logger.warning("import_fetch_failed", source=source, error=str(exc))
                skipped.extend(
                    SkippedImport(
                        source=source, external_id=ref.external_id, reason="provider_error"
                    )
                    for ref in source_refs
                )
                continue
            returned = {result.external_id: result for result in results}
            for ref in source_refs:
                result = returned.get(ref.external_id)
                if result is None and source == "arxiv":
                    result = returned.get(normalize_arxiv_id(ref.external_id))
                if result is None:
                    skipped.append(
                        SkippedImport(
                            source=source, external_id=ref.external_id, reason="not_found"
                        )
                    )
                else:
                    fetched[(ref.source, ref.external_id)] = result

        imported = await self._persist_verified(actor, project_id, ordered_refs, fetched)
        return imported, skipped

    async def _persist_verified(
        self,
        actor: User,
        project_id: uuid.UUID,
        ordered_refs: list[PaperImportRef],
        fetched: dict[tuple[str, str], PaperResult],
    ) -> list[Paper]:
        if not fetched:
            return []

        # Set-based dedup: (source, external_id) pairs plus cross-source
        # DOI / arXiv-id matches, in two queries.
        provider_keys = [(r.source, r.external_id) for r in fetched.values()]
        existing_rows = await self.papers.get_existing_keys(project_id, provider_keys)
        existing_by_key = {(p.source, p.external_id): p for p in existing_rows}

        dois: list[str] = []
        arxiv_ids: list[str] = []
        for result in fetched.values():
            if result.doi:
                dois.append(normalize_doi(result.doi))
            aid = self._result_arxiv_id(result)
            if aid:
                arxiv_ids.append(aid)
        cross_rows = await self.papers.find_by_dois_or_arxiv_ids(
            project_id, dois=dois, arxiv_ids=arxiv_ids
        )
        by_doi = {p.doi: p for p in cross_rows if p.doi}
        by_arxiv = {p.arxiv_id: p for p in cross_rows if p.arxiv_id}

        def _existing_for(result: PaperResult) -> Paper | None:
            row = existing_by_key.get((result.source, result.external_id))
            if row is not None:
                return row
            if result.doi and (row := by_doi.get(normalize_doi(result.doi))) is not None:
                return row
            aid = self._result_arxiv_id(result)
            if aid and (row := by_arxiv.get(aid)) is not None:
                return row
            return None

        to_create: dict[tuple[str, str], Paper] = {}
        resolved: dict[tuple[str, str], Paper] = {}
        for ref_key, result in fetched.items():
            existing = _existing_for(result)
            if existing is not None:
                resolved[ref_key] = existing
                continue
            provider_key = (result.source, result.external_id)
            if provider_key in to_create:
                resolved[ref_key] = to_create[provider_key]
                continue
            paper = self._build_paper(actor, project_id, result)
            to_create[provider_key] = paper
            resolved[ref_key] = paper

        new_papers = list(to_create.values())
        if new_papers:
            try:
                await self.papers.add_all(new_papers)
                await self.db.commit()
            except IntegrityError:
                # Concurrent import created the same key: re-read and retry
                # the remainder once instead of surfacing a 500.
                await self.db.rollback()
                existing_rows = await self.papers.get_existing_keys(
                    project_id, list(to_create.keys())
                )
                existing_by_key = {(p.source, p.external_id): p for p in existing_rows}
                retry_papers: list[Paper] = []
                for provider_key, paper in to_create.items():
                    row = existing_by_key.get(provider_key)
                    if row is not None:
                        for ref_key, target in list(resolved.items()):
                            if target is paper:
                                resolved[ref_key] = row
                    else:
                        retry_papers.append(paper)
                if retry_papers:
                    await self.papers.add_all(retry_papers)
                    await self.db.commit()
                new_papers = retry_papers
            for paper in new_papers:
                _dispatch_ingest(paper.id)

        imported: list[Paper] = []
        seen_ids: set[uuid.UUID] = set()
        for ref in ordered_refs:
            entry = resolved.get((ref.source, ref.external_id))
            if entry is not None and entry.id not in seen_ids:
                seen_ids.add(entry.id)
                imported.append(entry)
        return imported

    @staticmethod
    def _result_arxiv_id(result: PaperResult) -> str | None:
        if result.source == "arxiv":
            return normalize_arxiv_id(result.external_id)
        raw = result.extra.get("arxiv_id")
        return normalize_arxiv_id(raw) if isinstance(raw, str) and raw else None

    def _build_paper(self, actor: User, project_id: uuid.UUID, result: PaperResult) -> Paper:
        primary = result.extra.get("arxiv_primary_category")
        return Paper(
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
            doi=normalize_doi(result.doi) if result.doi else None,
            arxiv_id=self._result_arxiv_id(result),
            primary_category=primary if isinstance(primary, str) else None,
            citation_count=result.citation_count,
            ingest_status=PaperIngestStatus.PENDING,
            metadata_json=result.extra,
            imported_by=actor.id,
        )

    # --- library -------------------------------------------------------------
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

    async def get_references(
        self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID
    ) -> dict[str, int]:
        """Delete preflight: per-category counts of artifacts citing the paper."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        return await self.papers.reference_counts(project_id, paper_id)

    async def delete(
        self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID, *, force: bool = False
    ) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        if not force:
            references = await self.papers.reference_counts(project_id, paper_id)
            if any(references.values()):
                raise PaperHasReferencesError(
                    details={"paper_id": str(paper_id), "references": references}
                )
        await self.papers.delete(paper)
        await self.db.commit()

    # --- sections ------------------------------------------------------------
    async def get_sections(
        self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID
    ) -> tuple[Paper, list[PaperSection]]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        sections = await self.sections.list_by_paper(paper.id)
        return paper, sections

    async def sections_for_agent(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        paper_key: str,
        kind: str | None = None,
        seq: int | None = None,
    ) -> dict:
        """Tool-shaped section read: items carry ``source``/``external_id`` so
        the ToolBroker whitelists the paper for citations automatically."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        source, _, external_id = paper_key.partition(":")
        if not source or not external_id:
            return {
                "results": [],
                "ingest_status": "unknown",
                "error": "paper_key must look like 'source:external_id'",
            }
        paper = await self.papers.get_by_external(project_id, source, external_id)
        if paper is None:
            return {
                "results": [],
                "ingest_status": "unknown",
                "error": f"Paper {paper_key} is not in the project library.",
            }

        sections = await self.sections.list_by_paper(paper.id)
        if not sections and paper.abstract:
            # Un-ingested paper: degrade to the abstract as a pseudo-section.
            sections = [
                PaperSection(
                    paper_id=paper.id,
                    seq=0,
                    level=1,
                    heading="Abstract",
                    body=paper.abstract,
                    char_count=len(paper.abstract),
                    kind=PaperSectionKind.ABSTRACT,
                )
            ]
        if kind is not None:
            sections = [s for s in sections if s.kind.value == kind]
        if seq is not None:
            sections = [s for s in sections if s.seq == seq]

        return {
            "results": [
                {
                    "source": paper.source,
                    "external_id": paper.external_id,
                    "title": paper.title,
                    "url": paper.url,
                    "seq": section.seq,
                    "heading": section.heading,
                    "kind": section.kind.value,
                    "level": section.level,
                    "body": section.body[:_AGENT_SECTION_BODY_MAX],
                }
                for section in sections
            ],
            "ingest_status": paper.ingest_status.value,
        }

    async def trigger_ingest(
        self, actor: User, project_id: uuid.UUID, paper_id: uuid.UUID
    ) -> Paper:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")
        if paper.ingest_status is PaperIngestStatus.RUNNING:
            raise IngestRunningError()
        paper.ingest_status = PaperIngestStatus.PENDING
        paper.ingest_error = None
        await self.db.commit()
        _dispatch_ingest(paper.id)
        return paper


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
            if status is IdeaStatus.ACTIVE:
                # Serialize direction approval per project so two concurrent
                # requests cannot both become active before the archive update.
                await self.db.execute(
                    select(Project.id).where(Project.id == project_id).with_for_update()
                )
                critique_id = await self.db.scalar(
                    select(ResearchCritique.id)
                    .where(
                        ResearchCritique.project_id == project_id,
                        ResearchCritique.idea_id == idea.id,
                    )
                    .limit(1)
                )
                if critique_id is None:
                    raise ValidationError(
                        "Run and review at least one critic report before approving a direction."
                    )
                await self.db.execute(
                    update(Idea)
                    .where(
                        Idea.project_id == project_id,
                        Idea.id != idea.id,
                        Idea.status == IdeaStatus.ACTIVE,
                    )
                    .values(status=IdeaStatus.ARCHIVED)
                )
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
