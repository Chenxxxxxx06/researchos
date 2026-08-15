"""Approved GitHub repository import and coding-agent handoff."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.coding_chat.service import CodingChatService
from researchos.common.config import get_settings
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.paths import is_denied, resolve_in_workspace, workspace_root_for
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.llm_config.models import LLMProviderConfig
from researchos.projects.service import ProjectService
from researchos.research.enums import IdeaStatus
from researchos.research.models import Idea

from .models import RepositorySnapshot
from .runner import GitDisabled, GitError, git_available, run_git
from .service import GitService

_GITHUB_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_LICENSE_NAMES = {"license", "license.txt", "license.md", "copying", "notice"}


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    repo: str
    canonical_url: str


@dataclass(frozen=True)
class MaterializedRepository:
    commit_sha: str
    default_branch: str | None
    license_spdx: str | None
    license_path: str | None
    file_count: int
    total_bytes: int
    skipped_files: list[dict]
    submodules: list[dict]
    manifest_hash: str


def validate_github_url(value: str) -> GitHubRepository:
    """Accept only a public GitHub HTTPS owner/repository URL."""

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(
            "Use a public GitHub HTTPS URL such as https://github.com/owner/repo."
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError(
            "Use a public GitHub HTTPS URL such as https://github.com/owner/repo."
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValidationError("The GitHub URL must identify exactly one owner and repository.")
    owner, repo = parts
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not _GITHUB_SEGMENT_RE.fullmatch(owner) or not _GITHUB_SEGMENT_RE.fullmatch(repo):
        raise ValidationError("The GitHub owner or repository name is invalid.")
    return GitHubRepository(
        owner=owner,
        repo=repo,
        canonical_url=f"https://github.com/{owner}/{repo}",
    )


def _license_identifier(text: str) -> str | None:
    lower = text.lower()
    if "apache license" in lower and "version 2.0" in lower:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in lower:
        return "MIT"
    if "gnu affero general public license" in lower:
        return "AGPL"
    if "gnu lesser general public license" in lower:
        return "LGPL"
    if "gnu general public license" in lower:
        return "GPL"
    if "mozilla public license" in lower:
        return "MPL-2.0"
    if "redistribution and use in source and binary forms" in lower:
        return "BSD"
    return None


def _read_submodules(root: Path) -> list[dict]:
    if not (root / ".gitmodules").is_file():
        return []
    result = run_git(
        root,
        "config",
        "--file",
        ".gitmodules",
        "--get-regexp",
        r"^submodule\..*\.(path|url)$",
        check=False,
    )
    entries: dict[str, dict] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        match = re.match(r"^submodule\.(.*)\.(path|url)$", key)
        if not match:
            continue
        name, field = match.groups()
        entries.setdefault(name, {"name": name})[field] = value.strip()
    return list(entries.values())


def _tracked_entries(root: Path) -> list[tuple[str, str]]:
    """Return ``(git_mode, path)`` without trusting checkout file types."""

    result = run_git(root, "ls-files", "--stage", "-z")
    entries: list[tuple[str, str]] = []
    for record in result.stdout.split("\0"):
        metadata, separator, path = record.partition("\t")
        mode = metadata.split(" ", 1)[0]
        if separator and path and mode:
            entries.append((mode, path))
    return entries


def _materialize_repository_sync(
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    source: GitHubRepository,
    destination_path: str,
) -> MaterializedRepository:
    settings = get_settings()
    workspace = workspace_root_for(project_id).resolve()
    destination = resolve_in_workspace(project_id, destination_path)
    if destination.exists():
        raise ConflictError("The repository snapshot destination already exists.")

    staging_root = workspace / ".ros-staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = staging_root / f"repository-{snapshot_id.hex}"
    if staging.exists():
        shutil.rmtree(staging)

    try:
        with tempfile.TemporaryDirectory(prefix="researchos-repository-") as temp:
            temp_root = Path(temp)
            clone = temp_root / "repository"
            try:
                run_git(
                    temp_root,
                    "clone",
                    "--depth",
                    "1",
                    "--single-branch",
                    "--no-tags",
                    "--no-recurse-submodules",
                    f"{source.canonical_url}.git",
                    str(clone),
                    timeout=settings.repository_import_timeout_seconds,
                )
            except GitError as exc:
                raise ValidationError(
                    "The public GitHub repository could not be cloned. Check the URL and access."
                ) from exc

            commit_sha = run_git(clone, "rev-parse", "HEAD").stdout.strip()
            branch_result = run_git(clone, "symbolic-ref", "--short", "HEAD", check=False)
            branch = branch_result.stdout.strip() or None
            submodules = _read_submodules(clone)
            entries = _tracked_entries(clone)
            if len(entries) > settings.repository_import_max_files:
                raise ValidationError(
                    "Repository has too many tracked files "
                    f"(limit {settings.repository_import_max_files})."
                )

            staging.mkdir()
            skipped: list[dict] = []
            total_bytes = 0
            copied = 0
            manifest = hashlib.sha256()
            license_path: str | None = None
            license_spdx: str | None = None

            for git_mode, raw_path in entries:
                pure = PurePosixPath(raw_path)
                if pure.is_absolute() or ".." in pure.parts or is_denied(raw_path):
                    skipped.append({"path": raw_path, "reason": "protected_path"})
                    continue
                if git_mode == "120000":
                    skipped.append({"path": raw_path, "reason": "symlink"})
                    continue
                if git_mode == "160000":
                    skipped.append({"path": raw_path, "reason": "submodule"})
                    continue
                source_file = clone.joinpath(*pure.parts)
                try:
                    resolved_source = source_file.resolve(strict=True)
                except (OSError, RuntimeError):
                    skipped.append({"path": raw_path, "reason": "unavailable"})
                    continue
                if source_file.is_symlink():
                    skipped.append({"path": raw_path, "reason": "symlink"})
                    continue
                if not resolved_source.is_relative_to(clone.resolve()) or not source_file.is_file():
                    skipped.append({"path": raw_path, "reason": "non_file"})
                    continue
                size = source_file.stat().st_size
                if size > settings.repository_import_max_file_bytes:
                    raise ValidationError(
                        f"Repository file {raw_path!r} exceeds the per-file import limit."
                    )
                total_bytes += size
                if total_bytes > settings.repository_import_max_total_bytes:
                    raise ValidationError("Repository exceeds the total import size limit.")

                target = staging.joinpath(*pure.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target)
                digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
                manifest.update(raw_path.encode("utf-8", errors="surrogateescape"))
                manifest.update(b"\0")
                manifest.update(digest.encode("ascii"))
                manifest.update(b"\0")
                copied += 1

                if license_path is None and pure.name.lower() in _LICENSE_NAMES:
                    license_path = raw_path
                    license_spdx = _license_identifier(
                        source_file.read_text(encoding="utf-8", errors="replace")[:100_000]
                    )

            if copied == 0:
                raise ValidationError("The repository contains no importable tracked files.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, destination)
            return MaterializedRepository(
                commit_sha=commit_sha,
                default_branch=branch,
                license_spdx=license_spdx,
                license_path=license_path,
                file_count=copied,
                total_bytes=total_bytes,
                skipped_files=skipped,
                submodules=submodules,
                manifest_hash=manifest.hexdigest(),
            )
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _remove_materialized_sync(project_id: uuid.UUID, destination_path: str) -> None:
    destination = resolve_in_workspace(project_id, destination_path)
    if destination.exists() and destination.is_dir():
        shutil.rmtree(destination)


class RepositorySnapshotService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def list(
        self, actor: User, project_id: uuid.UUID, *, idea_id: uuid.UUID | None = None
    ) -> list[RepositorySnapshot]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        query = select(RepositorySnapshot).where(RepositorySnapshot.project_id == project_id)
        if idea_id is not None:
            query = query.where(RepositorySnapshot.idea_id == idea_id)
        result = await self.db.execute(query.order_by(RepositorySnapshot.created_at.desc()))
        return list(result.scalars().all())

    async def import_repository(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        idea_id: uuid.UUID,
        github_url: str,
    ) -> RepositorySnapshot:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        if not git_available():
            raise GitDisabled()
        idea = await self.db.get(Idea, idea_id)
        if idea is None or idea.project_id != project_id:
            raise NotFoundError("Idea not found.")
        if idea.status is not IdeaStatus.ACTIVE:
            raise ConflictError(
                "Approve this research direction before importing implementation code.",
                code="direction_not_approved",
            )
        source = validate_github_url(github_url)
        snapshot_id = uuid.uuid4()
        destination_path = (
            f"sources/{source.owner.lower()}-{source.repo.lower()}-{snapshot_id.hex[:8]}"
        )
        snapshot = RepositorySnapshot(
            id=snapshot_id,
            project_id=project_id,
            idea_id=idea.id,
            approved_by=actor.id,
            source_url=source.canonical_url,
            source_owner=source.owner,
            source_repo=source.repo,
            destination_path=destination_path,
            status="importing",
        )
        self.db.add(snapshot)
        await self.db.commit()

        materialized = False
        try:
            result = await asyncio.to_thread(
                _materialize_repository_sync,
                project_id,
                snapshot.id,
                source,
                destination_path,
            )
            materialized = True
            workspace_sha = await GitService(self.db).commit_repository_snapshot(
                project_id,
                snapshot_id=snapshot.id,
                source_url=source.canonical_url,
                source_commit_sha=result.commit_sha,
                destination_path=destination_path,
                actor=actor,
            )
        except Exception as exc:
            await self.db.rollback()
            if materialized:
                await asyncio.to_thread(_remove_materialized_sync, project_id, destination_path)
            failed = await self.db.get(RepositorySnapshot, snapshot.id)
            if failed is not None:
                failed.status = "failed"
                failed.error = str(exc)[:2000]
                await self.db.commit()
            raise

        snapshot.commit_sha = result.commit_sha
        snapshot.default_branch = result.default_branch
        snapshot.license_spdx = result.license_spdx
        snapshot.license_path = result.license_path
        snapshot.file_count = result.file_count
        snapshot.total_bytes = result.total_bytes
        snapshot.skipped_files_json = result.skipped_files
        snapshot.submodules_json = result.submodules
        snapshot.manifest_hash = result.manifest_hash
        snapshot.workspace_commit_sha = workspace_sha
        snapshot.imported_at = datetime.now(tz=UTC)
        snapshot.status = "ready"
        snapshot.error = None
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def start_coding(
        self, actor: User, project_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> tuple[RepositorySnapshot, uuid.UUID, uuid.UUID]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        snapshot = await self.db.get(RepositorySnapshot, snapshot_id)
        if snapshot is None or snapshot.project_id != project_id:
            raise NotFoundError("Repository snapshot not found.")
        if snapshot.status != "ready":
            raise ConflictError("The repository snapshot is not ready for coding.")
        if snapshot.coding_session_id is not None and snapshot.coding_run_id is not None:
            return snapshot, snapshot.coding_session_id, snapshot.coding_run_id

        idea = await self.db.get(Idea, snapshot.idea_id)
        if idea is None or idea.project_id != project_id or idea.status is not IdeaStatus.ACTIVE:
            raise ConflictError(
                "The linked research direction is no longer active.",
                code="direction_not_active",
            )
        active_config = await self.db.scalar(
            select(LLMProviderConfig.id)
            .where(
                LLMProviderConfig.project_id == project_id,
                LLMProviderConfig.is_active.is_(True),
            )
            .limit(1)
        )
        if active_config is None:
            raise ConflictError(
                "Configure and test an active model before starting the Coding Agent.",
                code="real_llm_required",
            )

        chat = CodingChatService(self.db)
        session = await chat.create_session(
            actor,
            project_id,
            title=f"{idea.title} · {snapshot.source_owner}/{snapshot.source_repo}",
        )
        prompt = (
            f"Implement the first small, verifiable step for the approved research direction "
            f"'{idea.title}'. Hypothesis: {idea.hypothesis or 'not specified'}. "
            f"The approved repository snapshot is at {snapshot.destination_path} and is pinned "
            f"to source commit {snapshot.commit_sha}. Inspect its README, license, tests, and "
            "existing architecture first. Work only inside that snapshot directory. Do not run "
            "untrusted repository scripts or claim experimental results. Produce a minimal "
            "reviewable patch; the user will approve it before application."
        )
        message, run = await chat.post_message(
            actor, project_id, session.id, message=prompt[:10_000]
        )
        del message
        snapshot.coding_session_id = session.id
        snapshot.coding_run_id = run.id
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot, session.id, run.id
