"""Skill data access."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import SkillVisibility
from .models import Skill, SkillInstallation, SkillVersion


class SkillRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_slug(self, slug: str) -> Skill | None:
        return await self.db.scalar(select(Skill).where(Skill.slug == slug))

    async def latest_version(self, skill_id: uuid.UUID) -> SkillVersion | None:
        return await self.db.scalar(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.created_at.desc())
        )

    async def version_by_value(self, skill_id: uuid.UUID, version: str) -> SkillVersion | None:
        return await self.db.scalar(
            select(SkillVersion).where(
                SkillVersion.skill_id == skill_id, SkillVersion.version == version
            )
        )

    async def list_catalog(self, project_id: uuid.UUID) -> list[Skill]:
        """First-party skills plus this project's custom skills."""

        result = await self.db.execute(
            select(Skill)
            .where(
                or_(
                    Skill.visibility == SkillVisibility.FIRST_PARTY,
                    Skill.project_id == project_id,
                )
            )
            .order_by(Skill.visibility, Skill.name)
        )
        return list(result.scalars().all())

    async def add_skill(self, skill: Skill) -> Skill:
        self.db.add(skill)
        await self.db.flush()
        return skill

    async def add_version(self, version: SkillVersion) -> SkillVersion:
        self.db.add(version)
        await self.db.flush()
        return version


class InstallationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, project_id: uuid.UUID, skill_id: uuid.UUID) -> SkillInstallation | None:
        return await self.db.scalar(
            select(SkillInstallation).where(
                SkillInstallation.project_id == project_id,
                SkillInstallation.skill_id == skill_id,
            )
        )

    async def list_for_project(self, project_id: uuid.UUID) -> list[SkillInstallation]:
        result = await self.db.execute(
            select(SkillInstallation).where(SkillInstallation.project_id == project_id)
        )
        return list(result.scalars().all())

    async def add(self, installation: SkillInstallation) -> SkillInstallation:
        self.db.add(installation)
        await self.db.flush()
        return installation
