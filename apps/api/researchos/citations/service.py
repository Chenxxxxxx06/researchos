"""Citation audit access and deterministic metadata analysis."""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.documents.bibtex import bib_key_for, bibtex_entry
from researchos.identity.models import User
from researchos.knowledge.models import MissionPaper
from researchos.missions.models import ResearchMission
from researchos.projects.service import ProjectService
from researchos.research.models import Paper

from .models import MissionCitationAudit


class CitationAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def validate_mission(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID, *, write: bool
    ) -> ResearchMission:
        await ProjectService(self.db).ensure_access(
            actor, project_id, ProjectRole.RESEARCHER if write else ProjectRole.VIEWER
        )
        mission = await self.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != project_id:
            raise NotFoundError("Research mission not found.")
        return mission

    async def list_audits(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[MissionCitationAudit]:
        await self.validate_mission(actor, project_id, mission_id, write=False)
        return list(
            (
                await self.db.execute(
                    select(MissionCitationAudit)
                    .where(MissionCitationAudit.mission_id == mission_id)
                    .order_by(MissionCitationAudit.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )


async def mission_papers(db: AsyncSession, mission_id: uuid.UUID) -> list[Paper]:
    return list(
        (
            await db.execute(
                select(Paper)
                .join(MissionPaper, MissionPaper.paper_id == Paper.id)
                .where(MissionPaper.mission_id == mission_id)
                .order_by(Paper.title)
            )
        )
        .scalars()
        .all()
    )


def build_citation_audit(papers: list[Paper]) -> tuple[list[dict], list[dict], int, str]:
    items: list[dict] = []
    groups: dict[str, list[str]] = defaultdict(list)
    bibtex: list[str] = []
    used_keys: dict[str, int] = defaultdict(int)
    missing_count = 0
    for paper in papers:
        missing: list[str] = []
        if not paper.authors_json:
            missing.append("authors")
        if paper.published_at is None:
            missing.append("year")
        if not paper.venue and paper.source != "arxiv":
            missing.append("venue")
        if not paper.doi and not paper.arxiv_id:
            missing.append("doi_or_arxiv")
        if not paper.url:
            missing.append("url")
        missing_count += len(missing)
        base_key = bib_key_for(paper)
        used_keys[base_key] += 1
        key = base_key if used_keys[base_key] == 1 else f"{base_key}{used_keys[base_key]}"
        duplicate_key = _duplicate_key(paper)
        groups[duplicate_key].append(str(paper.id))
        items.append(
            {
                "paper_id": str(paper.id),
                "citation_key": key,
                "title": paper.title,
                "authors": paper.authors_json,
                "year": paper.published_at.year if paper.published_at else None,
                "venue": paper.venue,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "url": paper.url,
                "missing_fields": missing,
                "status": "complete" if not missing else "needs_metadata",
            }
        )
        bibtex.append(bibtex_entry(paper, key))
    duplicates = [
        {"match_key": key, "paper_ids": ids, "count": len(ids)}
        for key, ids in groups.items()
        if len(ids) > 1
    ]
    return items, duplicates, missing_count, "\n".join(bibtex)


def _duplicate_key(paper: Paper) -> str:
    if paper.doi:
        return "doi:" + paper.doi.strip().lower().removeprefix("https://doi.org/")
    if paper.arxiv_id:
        return "arxiv:" + paper.arxiv_id.strip().lower()
    title = unicodedata.normalize("NFKC", paper.title).lower()
    return "title:" + re.sub(r"\W+", "", title)
