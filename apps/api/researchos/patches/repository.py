"""Patch data access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import PatchFile, PatchProposal


class PatchRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, proposal: PatchProposal) -> PatchProposal:
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def get(self, project_id: uuid.UUID, patch_id: uuid.UUID) -> PatchProposal | None:
        result = await self.db.execute(
            select(PatchProposal)
            .where(PatchProposal.id == patch_id, PatchProposal.project_id == project_id)
            .options(selectinload(PatchProposal.files).selectinload(PatchFile.hunks))
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[PatchProposal], int]:
        total = await self.db.scalar(
            select(func.count())
            .select_from(PatchProposal)
            .where(PatchProposal.project_id == project_id)
        )
        result = await self.db.execute(
            select(PatchProposal)
            .where(PatchProposal.project_id == project_id)
            .options(selectinload(PatchProposal.files).selectinload(PatchFile.hunks))
            .order_by(PatchProposal.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)
