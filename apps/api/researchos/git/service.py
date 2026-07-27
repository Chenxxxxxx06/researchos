"""Git business logic: lazy init, status, log, commit diff, apply-commit, revert.

Everything degrades cleanly when git is unavailable (see the provider), and no
destructive history operation exists: revert is an additive inverse commit.
Subprocess work runs in ``asyncio.to_thread`` (P3-D14); mutating operations
take a per-project asyncio lock (git's own ``index.lock`` covers cross-process
races by turning them into logged failures).
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.paths import (
    is_denied,
    relative_to_root,
    resolve_in_workspace,
    workspace_root_for,
)
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.workspace import fs

from .provider import get_git_provider
from .runner import GitDisabled, git_available, run_git, validate_sha
from .schemas import (
    GitCommitDiff,
    GitCommitDiffFile,
    GitCommitEntry,
    GitRevertResponse,
    GitStatusResponse,
)

logger = structlog.get_logger(__name__)

_TRAILER_RE = re.compile(r"^(Patch|Agent-Run|Reverts):\s*(\S+)$", re.MULTILINE)
_CO_AUTHOR_LINE = "Co-Authored-By: codex <noreply@anthropic.com>"
_BOT_IDENT = ("user.name=ResearchOS", "user.email=bot@researchos.local")

# Per-project locks serializing apply-commit / revert within this process.
_project_locks: dict[str, asyncio.Lock] = {}


def _lock_for(project_id: uuid.UUID) -> asyncio.Lock:
    return _project_locks.setdefault(str(project_id), asyncio.Lock())


def _parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    if not value or value == "-":
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _extract_trailers(body: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _TRAILER_RE.finditer(body)}


class GitService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    # --- repo lifecycle ------------------------------------------------------
    def _ensure_repo_sync(self, project_id: uuid.UUID) -> bool:
        """Lazily initialize the per-workspace repo. Idempotent."""

        if not git_available():
            return False
        root = fs.ensure_workspace(project_id)
        if (root / ".git").exists():
            return True
        run_git(root, "init")
        run_git(root, "symbolic-ref", "HEAD", "refs/heads/main")
        run_git(root, "config", "user.name", "ResearchOS")
        run_git(root, "config", "user.email", "bot@researchos.local")
        # Capture any files that already existed before git was initialized, so
        # the working tree starts clean. Otherwise those files stay untracked and
        # every revert (which requires a clean tree) is permanently blocked.
        run_git(root, "add", "-A")
        # user.name / user.email already set in local config above; no -c needed.
        run_git(
            root,
            "commit",
            "--allow-empty",
            "-m",
            "researchos: initialize workspace",
        )
        return True

    async def ensure_repo(self, project_id: uuid.UUID) -> bool:
        return await asyncio.to_thread(self._ensure_repo_sync, project_id)

    # --- reads ---------------------------------------------------------------
    async def status(self, actor: User, project_id: uuid.UUID) -> GitStatusResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        provider = get_git_provider()
        return await asyncio.to_thread(provider.status, project_id)

    async def log(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        path: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[GitCommitEntry]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        if not git_available():
            return []
        root = workspace_root_for(project_id)
        if not (root / ".git").exists():
            return []

        args = [
            "log",
            "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%b%x1e",
            "-n",
            str(limit),
            "--skip",
            str(skip),
        ]
        if path:
            resolved = resolve_in_workspace(project_id, path)
            args += ["--", relative_to_root(project_id, resolved)]
        proc = await asyncio.to_thread(run_git, root, *args, check=False)
        if proc.returncode != 0:
            return []
        return self._parse_log(proc.stdout)

    def _parse_log(self, output: str) -> list[GitCommitEntry]:
        entries: list[GitCommitEntry] = []
        for record in output.split("\x1e"):
            record = record.strip("\n\r ")
            if not record:
                continue
            fields = record.split("\x1f")
            if len(fields) < 6:
                continue
            sha, author_name, author_email, authored_at, summary, body = fields[:6]
            trailers = _extract_trailers(body)
            try:
                authored = datetime.fromisoformat(authored_at)
            except ValueError:
                continue
            entries.append(
                GitCommitEntry(
                    sha=sha,
                    author_name=author_name,
                    author_email=author_email,
                    authored_at=authored,
                    summary=summary,
                    patch_id=_parse_optional_uuid(trailers.get("Patch")),
                    agent_run_id=_parse_optional_uuid(trailers.get("Agent-Run")),
                    reverts_sha=trailers.get("Reverts"),
                )
            )
        return entries

    async def commit_diff(self, actor: User, project_id: uuid.UUID, sha: str) -> GitCommitDiff:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        if not git_available():
            raise GitDisabled()
        validate_sha(sha)
        root = workspace_root_for(project_id)
        if not (root / ".git").exists():
            raise NotFoundError("Commit not found.")
        return await asyncio.to_thread(self._commit_diff_sync, project_id, root, sha)

    def _commit_diff_sync(self, project_id: uuid.UUID, root: Path, sha: str) -> GitCommitDiff:
        meta = run_git(
            root,
            "show",
            "--format=%H%x1f%an%x1f%aI%x1f%s",
            "--name-status",
            "--no-color",
            sha,
            check=False,
        )
        if meta.returncode != 0:
            raise NotFoundError("Commit not found.")
        lines = meta.stdout.splitlines()
        if not lines:
            raise NotFoundError("Commit not found.")
        full_sha, author_name, authored_at, summary = (lines[0].split("\x1f") + ["", "", ""])[:4]

        has_parent = (
            run_git(root, "rev-parse", "--verify", "--quiet", f"{sha}^", check=False).returncode
            == 0
        )

        files: list[GitCommitDiffFile] = []
        for line in lines[1:]:
            if not line.strip() or "\t" not in line:
                continue
            status, *paths = line.split("\t")
            status = status.strip()
            if not status or not paths:
                continue
            code = status[0]
            if code == "R" and len(paths) >= 2:
                old_path, path = paths[0], paths[1]
                change: str = "renamed"
            else:
                old_path, path = None, paths[0]
                change = {"A": "added", "M": "modified", "D": "deleted"}.get(code, "modified")
            if is_denied(path) or (old_path and is_denied(old_path)):
                continue

            old_content = old_size = None
            new_content = new_size = None
            omitted = False
            if change != "added" and has_parent:
                old_content, old_size, old_omitted = self._blob(root, f"{sha}^", old_path or path)
                omitted = omitted or old_omitted
            if change != "deleted":
                new_content, new_size, new_omitted = self._blob(root, sha, path)
                omitted = omitted or new_omitted
            files.append(
                GitCommitDiffFile(
                    path=path,
                    change_type=change,
                    old_path=old_path,
                    old_content=None if omitted else old_content,
                    new_content=None if omitted else new_content,
                    omitted=omitted,
                    size=int(new_size or old_size or 0),
                )
            )

        try:
            authored = datetime.fromisoformat(authored_at)
        except ValueError as exc:
            raise NotFoundError("Commit not found.") from exc
        return GitCommitDiff(
            sha=full_sha,
            summary=summary,
            author_name=author_name,
            authored_at=authored,
            files=files,
        )

    def _blob(self, root: Path, rev: str, path: str) -> tuple[str | None, int | None, bool]:
        """Return (content, size, omitted) for ``rev:path``."""

        from researchos.common.config import get_settings

        size_proc = run_git(root, "cat-file", "-s", f"{rev}:{path}", check=False)
        if size_proc.returncode != 0:
            return None, None, False
        try:
            size = int(size_proc.stdout.strip())
        except ValueError:
            return None, None, False
        if size > get_settings().workspace_max_file_bytes:
            return None, size, True
        show = run_git(root, "show", f"{rev}:{path}", check=False)
        if show.returncode != 0:
            return None, size, False
        if "\x00" in show.stdout:
            return None, size, True
        return show.stdout, size, False

    # --- mutations -----------------------------------------------------------
    async def commit_applied_patch(
        self,
        project_id: uuid.UUID,
        *,
        summary: str,
        patch_id: uuid.UUID,
        agent_run_id: uuid.UUID | None,
        author_name: str,
        author_email: str,
        paths: list[str],
    ) -> str | None:
        """Record an applied patch as a git commit. Never fails the apply."""

        try:
            if not await self.ensure_repo(project_id):
                return None
            async with _lock_for(project_id):
                return await asyncio.to_thread(
                    self._commit_applied_sync,
                    project_id,
                    summary,
                    patch_id,
                    agent_run_id,
                    author_name,
                    author_email,
                    paths,
                )
        except Exception as exc:  # noqa: BLE001 - git is traceability, not correctness
            logger.warning(
                "git_commit_failed",
                project_id=str(project_id),
                patch_id=str(patch_id),
                error=str(exc),
            )
            return None

    def _commit_applied_sync(
        self,
        project_id: uuid.UUID,
        summary: str,
        patch_id: uuid.UUID,
        agent_run_id: uuid.UUID | None,
        author_name: str,
        author_email: str,
        paths: list[str],
    ) -> str:
        root = workspace_root_for(project_id)
        rels = [relative_to_root(project_id, resolve_in_workspace(project_id, p)) for p in paths]
        run_git(root, "add", "-A", "--", *rels)
        first = (summary or "").strip().splitlines()[0][:72] if (summary or "").strip() else ""
        message = (
            f"{first or 'Apply patch'}\n"
            "\n"
            f"Patch: {patch_id}\n"
            f"Agent-Run: {agent_run_id or '-'}\n"
            "\n"
            f"{_CO_AUTHOR_LINE}\n"
        )
        run_git(
            root,
            "commit",
            "-m",
            message,
            "--author",
            f"{author_name} <{author_email}>",
        )
        return run_git(root, "rev-parse", "HEAD").stdout.strip()

    async def revert(self, actor: User, project_id: uuid.UUID, sha: str) -> GitRevertResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        if not git_available():
            raise GitDisabled()
        validate_sha(sha)
        root = workspace_root_for(project_id)
        if not (root / ".git").exists():
            raise NotFoundError("Commit not found.")
        async with _lock_for(project_id):
            return await asyncio.to_thread(self._revert_sync, root, sha, actor)

    def _revert_sync(self, root: Path, sha: str, actor: User) -> GitRevertResponse:
        full = run_git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}", check=False)
        if full.returncode != 0:
            raise NotFoundError("Commit not found.")
        full_sha = full.stdout.strip()

        dirty = run_git(root, "status", "--porcelain")
        if dirty.stdout.strip():
            raise ValidationError(
                "Workspace has uncommitted changes; apply or discard them before reverting.",
                http_status=400,
            )

        original_summary = run_git(root, "log", "-1", "--format=%s", full_sha).stdout.strip()
        attempt = run_git(root, "revert", "--no-commit", "--no-edit", full_sha, check=False)
        if attempt.returncode != 0:
            run_git(root, "revert", "--abort", check=False)  # best-effort cleanup
            stderr = (attempt.stderr or "").strip()[:300]
            raise ValidationError(f"Revert failed: {stderr}", http_status=400)

        message = (
            f'Revert "{original_summary}"\n'
            "\n"
            f"Reverts: {full_sha}\n"
            "\n"
            f"{_CO_AUTHOR_LINE}\n"
        )
        run_git(
            root,
            "commit",
            "--allow-empty",  # a no-op revert still records the audit trail
            "-m",
            message,
            "--author",
            f"{actor.display_name} <{actor.email}>",
        )
        commit_sha = run_git(root, "rev-parse", "HEAD").stdout.strip()
        return GitRevertResponse(commit_sha=commit_sha, reverted_sha=full_sha)
