"""Project data access."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import ProjectRole, ProjectStatus
from researchos.identity.models import User

from .models import Project, ProjectMembership


class ProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self.db.get(Project, project_id)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        description: str | None,
        field: str | None,
        created_by: uuid.UUID,
    ) -> Project:
        project = Project(
            organization_id=organization_id,
            name=name,
            description=description,
            field=field,
            created_by=created_by,
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def list_all_in_org(
        self, organization_id: uuid.UUID, *, include_archived: bool, limit: int, offset: int
    ) -> tuple[list[Project], int]:
        conditions = [Project.organization_id == organization_id]
        if not include_archived:
            conditions.append(Project.status == ProjectStatus.ACTIVE)

        total = await self.db.scalar(select(func.count()).select_from(Project).where(*conditions))
        result = await self.db.execute(
            select(Project)
            .where(*conditions)
            .order_by(Project.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_for_member_in_org(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Project], int]:
        conditions = [Project.organization_id == organization_id]
        if not include_archived:
            conditions.append(Project.status == ProjectStatus.ACTIVE)

        base = (
            select(Project)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id == user_id, *conditions)
        )
        total = await self.db.scalar(select(func.count()).select_from(base.subquery()))
        result = await self.db.execute(
            base.order_by(Project.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)


class ProjectMembershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectRole
    ) -> ProjectMembership:
        membership = ProjectMembership(project_id=project_id, user_id=user_id, role=role)
        self.db.add(membership)
        await self.db.flush()
        return membership

    async def get(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMembership | None:
        result = await self.db.execute(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_members(self, project_id: uuid.UUID) -> list[tuple[User, ProjectRole]]:
        result = await self.db.execute(
            select(User, ProjectMembership.role)
            .join(ProjectMembership, ProjectMembership.user_id == User.id)
            .where(ProjectMembership.project_id == project_id)
            .order_by(ProjectMembership.created_at)
        )
        return [(user, role) for user, role in result.all()]

    async def delete(self, membership: ProjectMembership) -> None:
        await self.db.delete(membership)
        await self.db.flush()
