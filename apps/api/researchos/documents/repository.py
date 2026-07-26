"""LaTeX document data access."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import SuggestionStatus
from .models import (
    DocumentFile,
    DocumentFileRevision,
    DocumentSuggestion,
    LatexCompileJob,
    LatexProject,
)


class LatexProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, latex_project: LatexProject) -> LatexProject:
        self.db.add(latex_project)
        await self.db.flush()
        return latex_project

    async def get(self, project_id: uuid.UUID, latex_project_id: uuid.UUID) -> LatexProject | None:
        lp = await self.db.get(LatexProject, latex_project_id)
        return lp if lp and lp.project_id == project_id else None

    async def list(self, project_id: uuid.UUID) -> list[LatexProject]:
        result = await self.db.execute(
            select(LatexProject)
            .where(LatexProject.project_id == project_id)
            .order_by(LatexProject.created_at.desc())
        )
        return list(result.scalars().all())


class DocumentFileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, file: DocumentFile) -> DocumentFile:
        self.db.add(file)
        await self.db.flush()
        return file

    async def get_by_path(self, latex_project_id: uuid.UUID, path: str) -> DocumentFile | None:
        result = await self.db.execute(
            select(DocumentFile).where(
                DocumentFile.latex_project_id == latex_project_id, DocumentFile.path == path
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, latex_project_id: uuid.UUID, file_id: uuid.UUID
    ) -> DocumentFile | None:
        file = await self.db.get(DocumentFile, file_id)
        return file if file and file.latex_project_id == latex_project_id else None

    async def list(self, latex_project_id: uuid.UUID) -> list[DocumentFile]:
        result = await self.db.execute(
            select(DocumentFile)
            .where(DocumentFile.latex_project_id == latex_project_id)
            .order_by(DocumentFile.path)
        )
        return list(result.scalars().all())


class DocumentRevisionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, revision: DocumentFileRevision) -> DocumentFileRevision:
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def get_by_version(
        self, document_file_id: uuid.UUID, version: int
    ) -> DocumentFileRevision | None:
        result = await self.db.execute(
            select(DocumentFileRevision).where(
                DocumentFileRevision.document_file_id == document_file_id,
                DocumentFileRevision.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(
        self, document_file_id: uuid.UUID, *, limit: int
    ) -> list[DocumentFileRevision]:
        result = await self.db.execute(
            select(DocumentFileRevision)
            .where(DocumentFileRevision.document_file_id == document_file_id)
            .order_by(DocumentFileRevision.version.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def prune(self, document_file_id: uuid.UUID, *, keep: int) -> None:
        """Delete revisions older than the newest ``keep`` for one file."""

        keep_versions = (
            select(DocumentFileRevision.version)
            .where(DocumentFileRevision.document_file_id == document_file_id)
            .order_by(DocumentFileRevision.version.desc())
            .limit(keep)
        ).scalar_subquery()
        await self.db.execute(
            delete(DocumentFileRevision).where(
                DocumentFileRevision.document_file_id == document_file_id,
                DocumentFileRevision.version.not_in(keep_versions),
            )
        )


class SuggestionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, suggestion: DocumentSuggestion) -> DocumentSuggestion:
        self.db.add(suggestion)
        await self.db.flush()
        return suggestion

    async def get(
        self, latex_project_id: uuid.UUID, suggestion_id: uuid.UUID
    ) -> DocumentSuggestion | None:
        suggestion = await self.db.get(DocumentSuggestion, suggestion_id)
        if suggestion is None or suggestion.latex_project_id != latex_project_id:
            return None
        return suggestion

    async def list_by_project(
        self,
        latex_project_id: uuid.UUID,
        *,
        status: SuggestionStatus | None,
        path: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[DocumentSuggestion, str]], int]:
        """Return ``[(suggestion, file_path)]`` newest-first plus the total."""

        conditions = [DocumentSuggestion.latex_project_id == latex_project_id]
        if status is not None:
            conditions.append(DocumentSuggestion.status == status)
        if path is not None:
            conditions.append(DocumentFile.path == path)
        join_clause = DocumentSuggestion.document_file_id == DocumentFile.id
        total = await self.db.scalar(
            select(func.count())
            .select_from(DocumentSuggestion)
            .join(DocumentFile, join_clause)
            .where(*conditions)
        )
        result = await self.db.execute(
            select(DocumentSuggestion, DocumentFile.path)
            .join(DocumentFile, join_clause)
            .where(*conditions)
            .order_by(DocumentSuggestion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [(row[0], row[1]) for row in result.all()]
        return rows, int(total or 0)


class CompileJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, job: LatexCompileJob) -> LatexCompileJob:
        self.db.add(job)
        await self.db.flush()
        return job

    async def get(self, latex_project_id: uuid.UUID, job_id: uuid.UUID) -> LatexCompileJob | None:
        job = await self.db.get(LatexCompileJob, job_id)
        return job if job and job.latex_project_id == latex_project_id else None
