"""LaTeX document data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DocumentFile, LatexCompileJob, LatexProject


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

    async def list(self, latex_project_id: uuid.UUID) -> list[DocumentFile]:
        result = await self.db.execute(
            select(DocumentFile)
            .where(DocumentFile.latex_project_id == latex_project_id)
            .order_by(DocumentFile.path)
        )
        return list(result.scalars().all())


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
