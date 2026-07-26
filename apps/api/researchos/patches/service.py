"""Patch proposal lifecycle and authorization.

Proposals may carry SEARCH/REPLACE edit blocks: the server resolves them
against a snapshotted base at proposal time, materializes ``new_content``, and
derives real diff hunks. Apply stays whole-file guarded by ``base_sha``
(optimistic concurrency) but is now atomic (staged + journaled renames with
rollback) and records a git commit when git is available.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import AppError, NotFoundError, ValidationError
from researchos.common.pagination import Page
from researchos.common.paths import resolve_in_workspace
from researchos.common.roles import ProjectRole
from researchos.git.service import GitService
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.workspace import fs
from researchos.workspace.fs import FileOp, WorkspaceApplyError

from .enums import PatchChangeType, PatchStatus
from .models import PatchFile, PatchHunk, PatchProposal
from .repository import PatchRepository
from .resolution import EditBlock, EditResolutionError, compute_hunks, resolve_edits
from .schemas import ApplyResultResponse, PatchConflict, PatchFileInput

if TYPE_CHECKING:
    from researchos.agents.models import AgentRun


def _failure(
    path: str, reason: str, *, index: int | None = None, detail: str | None = None
) -> dict:
    out: dict = {"path": path, "reason": reason}
    if index is not None:
        out["index"] = index
    if detail is not None:
        out["detail"] = detail
    return out


class PatchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.patches = PatchRepository(db)
        self.projects = ProjectService(db)

    def _validate_paths(self, project_id: uuid.UUID, files: list[PatchFileInput]) -> None:
        # Raises WorkspaceAccessError (403) for traversal / denied paths.
        for f in files:
            resolve_in_workspace(project_id, f.path)

    def _prepare_file(
        self, project_id: uuid.UUID, f: PatchFileInput
    ) -> tuple[PatchFile | None, list[dict]]:
        """Resolve one input file into a PatchFile row or per-file failures."""

        if f.change_type == PatchChangeType.CREATE:
            if fs.current_sha(project_id, f.path) is not None:
                return None, [_failure(f.path, "already_exists")]
            new_content = f.new_content or ""
            row = PatchFile(
                path=f.path,
                change_type=f.change_type,
                base_sha=None,
                new_content=new_content,
                base_content=None,
            )
            self._attach_hunks(row, "", new_content)
            return row, []

        try:
            data = fs.read_file(project_id, f.path)
        except NotFoundError:
            return None, [_failure(f.path, "base_missing")]

        unreadable = bool(data["binary"] or data["too_large"])

        if f.change_type == PatchChangeType.DELETE:
            row = PatchFile(
                path=f.path,
                change_type=f.change_type,
                base_sha=f.base_sha or data["sha"],
                new_content=None,
                base_content=None if unreadable else data["content"],
            )
            if not unreadable:
                self._attach_hunks(row, data["content"] or "", "")
            return row, []

        # MODIFY
        if unreadable:
            if f.edits:
                return None, [_failure(f.path, "unpatchable_binary")]
            # Whole-file replacement of an unreadable file: allowed, degraded
            # (no snapshot, no hunks) — matches legacy behavior.
            return (
                PatchFile(
                    path=f.path,
                    change_type=f.change_type,
                    base_sha=f.base_sha,
                    new_content=f.new_content,
                    base_content=None,
                ),
                [],
            )

        base_content: str = data["content"] or ""
        live_sha: str = data["sha"]
        edits_json: list | None = None
        if f.edits:
            # The agent read this file moments ago; a mismatch means the file
            # changed concurrently — resolving against it would be unsound.
            if live_sha != f.base_sha:
                return None, [_failure(f.path, "base_changed")]
            try:
                new_content = resolve_edits(
                    base_content, [EditBlock(search=e.search, replace=e.replace) for e in f.edits]
                )
            except EditResolutionError as exc:
                return None, [
                    _failure(f.path, fl.reason, index=fl.index) for fl in exc.failures
                ]
            edits_json = [{"search": e.search, "replace": e.replace} for e in f.edits]
        else:
            # Whole-file UI path: a stale base_sha is kept as-is — the
            # apply-time guard reports the conflict (unchanged semantics).
            new_content = f.new_content or ""

        row = PatchFile(
            path=f.path,
            change_type=f.change_type,
            base_sha=f.base_sha,
            new_content=new_content,
            base_content=base_content,
            edits_json=edits_json,
        )
        self._attach_hunks(row, base_content, new_content)
        return row, []

    @staticmethod
    def _attach_hunks(row: PatchFile, base: str, new: str) -> None:
        for h in compute_hunks(base, new):
            row.hunks.append(
                PatchHunk(
                    header=h.header,
                    old_start=h.old_start,
                    old_lines=h.old_lines,
                    new_start=h.new_start,
                    new_lines=h.new_lines,
                    content=h.content,
                )
            )

    async def create_proposal(
        self,
        *,
        project_id: uuid.UUID,
        created_by: uuid.UUID,
        summary: str,
        files: list[PatchFileInput],
        agent_run_id: uuid.UUID | None = None,
    ) -> tuple[PatchProposal | None, list[dict]]:
        """Build a pending proposal (no permission check — callers authorize).

        Returns ``(proposal_or_None, failures)``: files that fail resolution are
        excluded (all-or-nothing per *file*, not per proposal); with zero
        surviving files no proposal is created.
        """

        self._validate_paths(project_id, files)
        failures: list[dict] = []
        rows: list[PatchFile] = []
        for f in files:
            row, file_failures = self._prepare_file(project_id, f)
            failures.extend(file_failures)
            if row is not None:
                rows.append(row)

        if not rows:
            return None, failures

        proposal = PatchProposal(
            project_id=project_id,
            created_by=created_by,
            agent_run_id=agent_run_id,
            summary=summary,
            status=PatchStatus.PENDING,
        )
        proposal.files.extend(rows)
        await self.patches.add(proposal)
        return proposal, failures

    async def create_patch(
        self, actor: User, project_id: uuid.UUID, *, summary: str, files: list[PatchFileInput]
    ) -> PatchProposal:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal, failures = await self.create_proposal(
            project_id=project_id, created_by=actor.id, summary=summary, files=files
        )
        if failures or proposal is None:
            # The human REST path is strict: any failing file rejects the whole
            # request (agents instead surface failures as rejected_files).
            raise ValidationError(
                "One or more files failed to resolve.",
                http_status=400,
                details={"files": failures},
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
        self,
        actor: User,
        project_id: uuid.UUID,
        patch_id: uuid.UUID,
        *,
        paths: list[str] | None = None,
    ) -> ApplyResultResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        if proposal.status != PatchStatus.PENDING:
            raise ValidationError(f"Patch is {proposal.status.value}, not pending.")

        # Optional file-granular selection (partial apply).
        all_paths = [f.path for f in proposal.files]
        if paths is not None:
            requested = set(paths)
            unknown = sorted(requested - set(all_paths))
            if unknown:
                raise ValidationError(
                    "Unknown paths in selection.",
                    http_status=400,
                    details={"unknown_paths": unknown},
                )
            selected = [f for f in proposal.files if f.path in requested]
            skipped_paths = sorted(p for p in all_paths if p not in requested)
        else:
            selected = list(proposal.files)
            skipped_paths = []

        # 1) Detect conflicts against the live filesystem (nothing written yet).
        conflicts: list[PatchConflict] = []
        satisfied_deletes: set[str] = set()
        for f in selected:
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
            elif f.change_type == PatchChangeType.MODIFY:
                if current is None:
                    conflicts.append(
                        PatchConflict(
                            path=f.path,
                            expected_sha=f.base_sha,
                            actual_sha=None,
                            reason="file missing",
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
            else:  # DELETE
                if current is None:
                    satisfied_deletes.add(f.path)  # idempotent delete: no-op
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
            proposal.conflict_json = [c.model_dump() for c in conflicts]
            await self.db.commit()
            return ApplyResultResponse(
                patch_id=proposal.id,
                status=PatchStatus.CONFLICT,
                conflicts=conflicts,
                skipped_paths=skipped_paths,
            )

        # 2) Apply all selected files atomically (staging + journaled renames).
        ops: list[FileOp] = []
        for f in selected:
            if f.change_type in (PatchChangeType.CREATE, PatchChangeType.MODIFY):
                ops.append(FileOp(path=f.path, action="write", content=f.new_content or ""))
            elif f.path not in satisfied_deletes:
                ops.append(FileOp(path=f.path, action="delete"))
        try:
            fs.apply_files_atomic(project_id, ops)
        except WorkspaceApplyError as exc:
            state = "rolled back" if exc.rolled_back else "PARTIALLY applied (rollback failed)"
            raise AppError(
                f"Applying the patch failed and the workspace was {state}.",
                code="apply_failed",
                http_status=500,
            ) from exc

        # 3) Record a git commit (traceability; never fails the apply).
        commit_sha = await GitService(self.db).commit_applied_patch(
            project_id,
            summary=proposal.summary,
            patch_id=proposal.id,
            agent_run_id=proposal.agent_run_id,
            author_name=actor.display_name,
            author_email=actor.email,
            paths=[f.path for f in selected],
        )

        proposal.status = PatchStatus.APPLIED
        proposal.applied_at = datetime.now(tz=UTC)
        proposal.applied_commit_sha = commit_sha
        await self.db.commit()
        return ApplyResultResponse(
            patch_id=proposal.id,
            status=PatchStatus.APPLIED,
            conflicts=[],
            applied_commit_sha=commit_sha,
            skipped_paths=skipped_paths,
        )

    async def reject_patch(
        self, actor: User, project_id: uuid.UUID, patch_id: uuid.UUID
    ) -> PatchProposal:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        if proposal.status not in (PatchStatus.PENDING, PatchStatus.CONFLICT):
            raise ValidationError(f"Patch is {proposal.status.value}, not pending or conflict.")
        proposal.status = PatchStatus.REJECTED
        await self.db.commit()
        return proposal

    async def repropose_patch(
        self, actor: User, project_id: uuid.UUID, patch_id: uuid.UUID
    ) -> AgentRun:
        """Seed a fresh coding run from a CONFLICT patch's originating run.

        The new run re-reads the conflicted files (its context carries
        ``repropose_of``); the agent's finalize links ``superseded_by`` and
        retires the old proposal.
        """

        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        proposal = await self.patches.get(project_id, patch_id)
        if proposal is None:
            raise NotFoundError("Patch not found.")
        if proposal.status != PatchStatus.CONFLICT:
            raise ValidationError(
                f"Patch is {proposal.status.value}, not conflict.", http_status=400
            )
        if proposal.agent_run_id is None:
            raise ValidationError(
                "Only agent-authored patches can be re-proposed.", http_status=400
            )

        from researchos.agents.enums import AgentType
        from researchos.agents.models import AgentRun
        from researchos.agents.service import AgentRunService

        origin = await self.db.get(AgentRun, proposal.agent_run_id)
        if origin is None:
            raise ValidationError("Originating agent run no longer exists.", http_status=400)
        message = str(origin.input_json.get("message", ""))
        old_context = dict(origin.input_json.get("context") or {})
        return await AgentRunService(self.db).create_run(
            actor,
            project_id,
            agent_type=AgentType.CODING,
            message=message,
            context={**old_context, "repropose_of": str(patch_id)},
        )
