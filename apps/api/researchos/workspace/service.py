"""Workspace business logic and authorization."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from . import fs
from .schemas import FileContentResponse, TreeNode, TreeResponse


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def get_tree(self, actor: User, project_id: uuid.UUID) -> TreeResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        nodes = [TreeNode.model_validate(n) for n in fs.build_tree(project_id)]
        return TreeResponse(root=str(project_id), nodes=nodes)

    async def read_file(self, actor: User, project_id: uuid.UUID, path: str) -> FileContentResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        data = fs.read_file(project_id, path)
        return FileContentResponse.model_validate(data)

    async def read_file_range(
        self,
        actor: User,
        project_id: uuid.UUID,
        path: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> dict:
        """Line-ranged read for the agent ``workspace.read`` tool (raw dict)."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return fs.read_file_range(project_id, path, start_line, end_line)

    async def grep(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        pattern: str,
        glob: str | None = None,
        max_results: int,
        ignore_case: bool = False,
    ) -> dict:
        """Bounded workspace grep (raw dict; may raise ``re.error``)."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return fs.grep_files(
            project_id,
            pattern,
            glob=glob,
            max_results=max_results,
            ignore_case=ignore_case,
        )
