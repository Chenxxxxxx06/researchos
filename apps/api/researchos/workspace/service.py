"""Workspace business logic and authorization."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus
from researchos.agents.models import AgentRun
from researchos.common.errors import ConflictError
from researchos.common.paths import (
    get_local_workspace_selection,
    reset_local_workspace_root,
    set_local_workspace_root,
    validate_local_workspace_root,
)
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.patches.enums import PatchStatus
from researchos.patches.models import PatchProposal
from researchos.projects.service import ProjectService

from . import fs
from .schemas import (
    FileContentResponse,
    LocalWorkspaceConfigResponse,
    TerminalRunResponse,
    TreeNode,
    TreeResponse,
)
from .terminal import run_command


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def get_tree(self, actor: User, project_id: uuid.UUID) -> TreeResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        nodes = [TreeNode.model_validate(n) for n in fs.build_tree(project_id)]
        return TreeResponse(root=str(fs.ensure_workspace(project_id)), nodes=nodes)

    async def get_local_config(
        self, actor: User, project_id: uuid.UUID
    ) -> LocalWorkspaceConfigResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return self._local_config_response(project_id)

    async def set_local_config(
        self, actor: User, project_id: uuid.UUID, root_path: str
    ) -> LocalWorkspaceConfigResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.ADMIN)
        root = validate_local_workspace_root(root_path)
        current = get_local_workspace_selection(project_id)
        if not current.uses_default and current.root == root:
            return self._local_config_response(project_id)
        await self._ensure_workspace_can_switch(project_id)
        set_local_workspace_root(project_id, root)
        return self._local_config_response(project_id)

    async def reset_local_config(
        self, actor: User, project_id: uuid.UUID
    ) -> LocalWorkspaceConfigResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.ADMIN)
        if get_local_workspace_selection(project_id).uses_default:
            return self._local_config_response(project_id)
        await self._ensure_workspace_can_switch(project_id)
        reset_local_workspace_root(project_id)
        return self._local_config_response(project_id)

    async def _ensure_workspace_can_switch(self, project_id: uuid.UUID) -> None:
        active_run = await self.db.scalar(
            select(AgentRun.id)
            .where(
                AgentRun.project_id == project_id,
                AgentRun.status.in_([AgentRunStatus.QUEUED, AgentRunStatus.RUNNING]),
            )
            .limit(1)
        )
        pending_patch = await self.db.scalar(
            select(PatchProposal.id)
            .where(
                PatchProposal.project_id == project_id,
                PatchProposal.status.in_([PatchStatus.PENDING, PatchStatus.CONFLICT]),
            )
            .limit(1)
        )
        if active_run is not None or pending_patch is not None:
            raise ConflictError(
                "The workspace cannot be switched while an Agent is running or a patch "
                "is awaiting review. Finish the run and apply or reject pending patches first.",
                code="workspace_switch_blocked",
                details={
                    "active_agent_run": str(active_run) if active_run else None,
                    "pending_patch": str(pending_patch) if pending_patch else None,
                },
            )

    @staticmethod
    def _local_config_response(project_id: uuid.UUID) -> LocalWorkspaceConfigResponse:
        selection = get_local_workspace_selection(project_id)
        return LocalWorkspaceConfigResponse(
            root=str(selection.root),
            default_root=str(selection.default_root),
            uses_default=selection.uses_default,
            available=selection.available,
            recent_roots=[str(item) for item in selection.recent_roots],
        )

    async def read_file(self, actor: User, project_id: uuid.UUID, path: str) -> FileContentResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        data = fs.read_file(project_id, path)
        return FileContentResponse.model_validate(data)

    async def save_file(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        path: str,
        content: str,
        base_sha: str | None,
    ) -> FileContentResponse:
        """Create or save a text file with optimistic concurrency protection."""

        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        actual_sha = fs.current_sha(project_id, path)
        if actual_sha != base_sha:
            raise ConflictError(
                "File changed on disk. Reload it before saving.",
                code="workspace_file_conflict",
                details={"path": path, "expected_sha": base_sha, "actual_sha": actual_sha},
            )
        fs.write_file(project_id, path, content)
        return FileContentResponse.model_validate(fs.read_file(project_id, path))

    async def run_terminal(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        argv: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> TerminalRunResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        result = await run_command(
            project_id,
            argv=argv,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        return TerminalRunResponse.model_validate(result)

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
