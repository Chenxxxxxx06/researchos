"""Project business logic and authorization.

All tenant-isolation and role checks live here (PHASE1_DECISIONS P1-D5/D6/D7).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import (
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)
from researchos.common.pagination import Page
from researchos.common.roles import (
    OrgRole,
    ProjectRole,
    ProjectStatus,
    project_role_satisfies,
)
from researchos.identity.models import User
from researchos.identity.repository import UserRepository
from researchos.organizations.service import OrganizationService

from .models import Project
from .repository import ProjectMembershipRepository, ProjectRepository


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.members = ProjectMembershipRepository(db)
        self.users = UserRepository(db)
        self.organizations = OrganizationService(db)

    # --- authorization core --------------------------------------------------
    async def _effective_role(self, actor: User, project: Project) -> ProjectRole | None:
        """Resolve the actor's effective role on a project, or None if no access.

        Explicit project membership wins; otherwise an org owner/admin gets an
        implicit project ``admin`` role.
        """

        membership = await self.members.get(project.id, actor.id)
        if membership is not None:
            return membership.role

        org_membership = await self.organizations.get_membership(actor.id, project.organization_id)
        if org_membership is not None and org_membership.role in (
            OrgRole.ADMIN,
            OrgRole.OWNER,
        ):
            return ProjectRole.ADMIN
        return None

    async def _load_with_access(
        self, actor: User, project_id: uuid.UUID, min_role: ProjectRole
    ) -> tuple[Project, ProjectRole]:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        role = await self._effective_role(actor, project)
        if role is None:
            # Hide existence from non-members (tenant isolation).
            raise NotFoundError("Project not found.")
        if not project_role_satisfies(role, min_role):
            raise PermissionError("Insufficient project role.")
        return project, role

    async def ensure_access(
        self, actor: User, project_id: uuid.UUID, min_role: ProjectRole = ProjectRole.VIEWER
    ) -> tuple[Project, ProjectRole]:
        """Public access guard for use by other bounded contexts (research, agents)."""

        return await self._load_with_access(actor, project_id, min_role)

    # --- commands ------------------------------------------------------------
    async def create_project(
        self,
        actor: User,
        *,
        organization_id: uuid.UUID,
        name: str,
        description: str | None,
        field: str | None,
    ) -> Project:
        # Any organization member may create a project and becomes its owner.
        await self.organizations.ensure_member(actor, organization_id, OrgRole.MEMBER)
        project = await self.projects.create(
            organization_id=organization_id,
            name=name,
            description=description,
            field=field,
            created_by=actor.id,
        )
        await self.members.create(project_id=project.id, user_id=actor.id, role=ProjectRole.OWNER)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def update_project(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        name: str | None,
        description: str | None,
        field: str | None,
    ) -> Project:
        project, _ = await self._load_with_access(actor, project_id, ProjectRole.ADMIN)
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if field is not None:
            project.field = field
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def archive_project(self, actor: User, project_id: uuid.UUID) -> Project:
        # Soft delete (P1-D7): requires project owner or org admin/owner.
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found.")

        role = await self._effective_role(actor, project)
        if role is None:
            raise NotFoundError("Project not found.")

        org_membership = await self.organizations.get_membership(actor.id, project.organization_id)
        is_org_admin = org_membership is not None and org_membership.role in (
            OrgRole.ADMIN,
            OrgRole.OWNER,
        )
        if not is_org_admin and not project_role_satisfies(role, ProjectRole.OWNER):
            raise PermissionError("Insufficient project role.")

        project.status = ProjectStatus.ARCHIVED
        await self.db.commit()
        await self.db.refresh(project)
        return project

    # --- queries -------------------------------------------------------------
    async def get_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project, _ = await self._load_with_access(actor, project_id, ProjectRole.VIEWER)
        return project

    async def list_projects(
        self,
        actor: User,
        *,
        organization_id: uuid.UUID,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> Page[Project]:
        membership = await self.organizations.ensure_member(actor, organization_id)
        if membership.role in (OrgRole.ADMIN, OrgRole.OWNER):
            items, total = await self.projects.list_all_in_org(
                organization_id, include_archived=include_archived, limit=limit, offset=offset
            )
        else:
            items, total = await self.projects.list_for_member_in_org(
                organization_id,
                actor.id,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
        return Page(items=items, total=total, limit=limit, offset=offset)

    # --- members -------------------------------------------------------------
    async def list_members(
        self, actor: User, project_id: uuid.UUID
    ) -> list[tuple[User, ProjectRole]]:
        await self._load_with_access(actor, project_id, ProjectRole.VIEWER)
        return await self.members.list_members(project_id)

    async def add_member(
        self, actor: User, project_id: uuid.UUID, *, email: str, role: ProjectRole
    ) -> tuple[User, ProjectRole]:
        project, _ = await self._load_with_access(actor, project_id, ProjectRole.ADMIN)

        user = await self.users.get_by_email(email.strip().lower())
        if user is None:
            raise NotFoundError("User not found.")
        # The target must already belong to the project's organization.
        org_membership = await self.organizations.get_membership(user.id, project.organization_id)
        if org_membership is None:
            raise ValidationError("User must be a member of the organization first.")
        if await self.members.get(project_id, user.id) is not None:
            raise ConflictError("User is already a project member.")

        await self.members.create(project_id=project_id, user_id=user.id, role=role)
        await self.db.commit()
        return user, role

    async def update_member_role(
        self, actor: User, project_id: uuid.UUID, target_user_id: uuid.UUID, role: ProjectRole
    ) -> tuple[User, ProjectRole]:
        await self._load_with_access(actor, project_id, ProjectRole.ADMIN)
        membership = await self.members.get(project_id, target_user_id)
        if membership is None:
            raise NotFoundError("Project member not found.")
        membership.role = role
        await self.db.commit()
        user = await self.users.get_by_id(target_user_id)
        assert user is not None
        return user, role

    async def remove_member(
        self, actor: User, project_id: uuid.UUID, target_user_id: uuid.UUID
    ) -> None:
        await self._load_with_access(actor, project_id, ProjectRole.ADMIN)
        membership = await self.members.get(project_id, target_user_id)
        if membership is None:
            raise NotFoundError("Project member not found.")
        await self.members.delete(membership)
        await self.db.commit()
