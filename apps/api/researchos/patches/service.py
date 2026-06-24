"""Patch proposal lifecycle and authorization.

Apply uses whole-file replacement guarded by ``base_sha`` (optimistic
concurrency, PHASE3-D4). On any conflict, nothing is written.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.pagination import Page
from researchos.common.paths import resolve_in_workspace
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.workspace import fs

from .enums import PatchChangeType, PatchStatus
from .models import PatchFile, PatchHunk, PatchProposal
from .repository import PatchRepository
from .schemas import ApplyResultResponse, PatchConflict, PatchFileInput


class PatchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.patches = PatchRepository(db)
        self.projects = ProjectService(db)

    def _validate_paths(self, project_id: uuid.UUID, files: list[PatchFileInput]) -> None:
        # Raises WorkspaceAccessError (403) for traversal / denied paths.
        for f in files:
            resolve_in_workspace(project_id, f.path)

    async def create_proposal(
        self,
        *,
        project_id: uuid.UUID,
        created_by: uuid.UUID,
        summary: str,
        files: list[PatchFileInput],
        agent_run_id: uuid.UUID | None = None,
    ) -> PatchProposal:
        """Build a pending proposal (no permission check — callers authorize)."""

        self._validate_paths(project_id, files)
        proposal = PatchProposal(
            project_id=project_id,
            created_by=created_by,
            agent_run_id=agent_run_id,
            summary=summary,
            status=PatchStatus.PENDING,
        )
        for f in files:
            patch_file = PatchFile(
                path=f.path,
                change_type=f.change_type,
                base_sha=f.base_sha,
                new_content=f.new_content,
            )
            for h in f.hunks:
                patch_file.hunks.append(
                    PatchHunk(
                        header=h.header,
                        old_start=h.old_start,
                        old_lines=h.old_lines,
                        new_start=h.new_start,
                        new_lines=h.new_lines,
                        content=h.content,
                    )
                )
            proposal.files.append(patch_file)
        return await self.patches.add(proposal)

    async def create_patch(
        self, actor: User, project_id: uuid.UUID, *, summary: str, files: list[PatchFileInput]
    ) -> PatchProposal:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.create_proposal(
            project_id=project_id, created_by=actor.id, summary=summary, files=files
        )
        await self.db.commit()
        loaded = await self.patches.get(project_id, proposal.id)
        assert loaded is not None
        return loaded

    async def list_patches(
        self, actor: User, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> Page[PatchProposal]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        items, total = await self.patches.list_by_project(project_id, limit=limit, offset=offset)
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get_patch(
        self, actor: User, project_id: uuid.UUID, patch_id: uuid.UUID
    ) -> PatchProposal:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        return proposal

    async def apply_patch(
        self, actor: User, project_id: uuid.UUID, patch_id: uuid.UUID
    ) -> ApplyResultResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        if proposal.status != PatchStatus.PENDING:
            raise ValidationError(f"Patch is {proposal.status.value}, not pending.")

        # 1) Detect conflicts against the live filesystem (nothing written yet).
        conflicts: list[PatchConflict] = []
        for f in proposal.files:
            resolve_in_workspace(project_id, f.path)  # re-guard
            current = fs.current_sha(project_id, f.path)
            if f.change_type == PatchChangeType.CREATE:
                if current is not None:
                    conflicts.append(
                        PatchConflict(
                            path=f.path,
                            expected_sha=None,
                            actual_sha=current,
                            reason="file already exists",
                        )
                    )
            elif current != f.base_sha:
                conflicts.append(
                    PatchConflict(
                        path=f.path,
                        expected_sha=f.base_sha,
                        actual_sha=current,
                        reason="base content changed",
                    )
                )

        if conflicts:
            proposal.status = PatchStatus.CONFLICT
            await self.db.commit()
            return ApplyResultResponse(
                patch_id=proposal.id, status=PatchStatus.CONFLICT, conflicts=conflicts
            )

        # 2) Apply all files.
        for f in proposal.files:
            if f.change_type in (PatchChangeType.CREATE, PatchChangeType.MODIFY):
                fs.write_file(project_id, f.path, f.new_content or "")
            else:
                fs.delete_file(project_id, f.path)

        proposal.status = PatchStatus.APPLIED
        proposal.applied_at = datetime.now(tz=UTC)
        await self.db.commit()
        return ApplyResultResponse(patch_id=proposal.id, status=PatchStatus.APPLIED, conflicts=[])

    async def reject_patch(
        self, actor: User, project_id: uuid.UUID, patch_id: uuid.UUID
    ) -> PatchProposal:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        if proposal.status != PatchStatus.PENDING:
            raise ValidationError(f"Patch is {proposal.status.value}, not pending.")
        proposal.status = PatchStatus.REJECTED
        await self.db.commit()
        return proposal
