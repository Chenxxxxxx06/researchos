"""Organization data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import OrgRole
from researchos.identity.models import User

from .models import Organization, OrganizationMembership


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        return await self.db.get(Organization, org_id)

    async def slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(select(Organization.id).where(Organization.slug == slug))
        return result.first() is not None

    async def create(self, *, name: str, slug: str, created_by: uuid.UUID) -> Organization:
        org = Organization(name=name, slug=slug, created_by=created_by)
        self.db.add(org)
        await self.db.flush()
        return org


class OrganizationMembershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, role: OrgRole
    ) -> OrganizationMembership:
        membership = OrganizationMembership(
            organization_id=organization_id, user_id=user_id, role=role
        )
        self.db.add(membership)
        await self.db.flush()
        return membership

    async def get(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMembership | None:
        result = await self.db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Organization, OrgRole]]:
        result = await self.db.execute(
            select(Organization, OrganizationMembership.role)
            .join(
                OrganizationMembership,
                OrganizationMembership.organization_id == Organization.id,
            )
            .where(OrganizationMembership.user_id == user_id)
            .order_by(Organization.created_at)
        )
        return [(org, role) for org, role in result.all()]

    async def list_members(self, organization_id: uuid.UUID) -> list[tuple[User, OrgRole]]:
        result = await self.db.execute(
            select(User, OrganizationMembership.role)
            .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.created_at)
        )
        return [(user, role) for user, role in result.all()]
