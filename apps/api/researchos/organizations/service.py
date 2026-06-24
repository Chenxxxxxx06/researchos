"""Organization business logic and authorization.

Permission checks (tenant isolation, role ladders) live here, per
PHASE1_DECISIONS P1-D5/D6.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, PermissionError
from researchos.common.roles import OrgRole, org_role_satisfies
from researchos.common.slug import random_suffix, slugify
from researchos.identity.models import User
from researchos.identity.repository import UserRepository

from .models import Organization, OrganizationMembership
from .repository import OrganizationMembershipRepository, OrganizationRepository


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.orgs = OrganizationRepository(db)
        self.memberships = OrganizationMembershipRepository(db)

    # --- slug helpers --------------------------------------------------------
    async def _unique_slug(self, base: str) -> str:
        slug = slugify(base)
        candidate = slug
        # Try a few times with a random suffix on collision.
        for _ in range(5):
            if not await self.orgs.slug_exists(candidate):
                return candidate
            candidate = f"{slug}-{random_suffix()}"
        # Extremely unlikely fall-through.
        return f"{slug}-{random_suffix(10)}"

    # --- creation ------------------------------------------------------------
    async def create_personal_organization(self, user: User) -> Organization:
        """Create the default organization for a freshly registered user."""

        base = user.display_name or user.email.split("@")[0]
        slug = await self._unique_slug(base)
        org = await self.orgs.create(
            name=f"{user.display_name}'s Workspace", slug=slug, created_by=user.id
        )
        await self.memberships.create(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER)
        return org

    async def create_organization(self, actor: User, name: str) -> Organization:
        slug = await self._unique_slug(name)
        org = await self.orgs.create(name=name, slug=slug, created_by=actor.id)
        await self.memberships.create(organization_id=org.id, user_id=actor.id, role=OrgRole.OWNER)
        await self.db.commit()
        return org

    # --- queries / authorization --------------------------------------------
    async def get_membership(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> OrganizationMembership | None:
        return await self.memberships.get(org_id, user_id)

    async def ensure_member(
        self, actor: User, org_id: uuid.UUID, min_role: OrgRole = OrgRole.MEMBER
    ) -> OrganizationMembership:
        """Return the actor's membership if it meets ``min_role``.

        Non-members get 404 (existence hidden); members with an insufficient
        role get 403.
        """

        membership = await self.memberships.get(org_id, actor.id)
        if membership is None:
            raise NotFoundError("Organization not found.")
        if not org_role_satisfies(membership.role, min_role):
            raise PermissionError("Insufficient organization role.")
        return membership

    async def list_for_user(self, actor: User) -> list[tuple[Organization, OrgRole]]:
        return await self.memberships.list_for_user(actor.id)

    async def get_organization(self, actor: User, org_id: uuid.UUID) -> Organization:
        await self.ensure_member(actor, org_id)
        org = await self.orgs.get_by_id(org_id)
        if org is None:
            raise NotFoundError("Organization not found.")
        return org

    async def list_members(self, actor: User, org_id: uuid.UUID) -> list[tuple[User, OrgRole]]:
        await self.ensure_member(actor, org_id)
        return await self.memberships.list_members(org_id)

    async def add_member(
        self, actor: User, org_id: uuid.UUID, *, email: str, role: OrgRole
    ) -> tuple[User, OrgRole]:
        """Add an existing user to an organization. Requires actor org admin+."""

        await self.ensure_member(actor, org_id, OrgRole.ADMIN)
        user = await UserRepository(self.db).get_by_email(email.strip().lower())
        if user is None:
            raise NotFoundError("User not found.")
        if await self.memberships.get(org_id, user.id) is not None:
            raise ConflictError("User is already an organization member.")
        await self.memberships.create(organization_id=org_id, user_id=user.id, role=role)
        await self.db.commit()
        return user, role
