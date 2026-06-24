"""Git status business logic (read-only)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .provider import get_git_provider
from .schemas import GitStatusResponse


class GitService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def status(self, actor: User, project_id: uuid.UUID) -> GitStatusResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return get_git_provider().status(project_id)
