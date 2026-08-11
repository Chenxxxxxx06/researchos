"""Workspace path guard (see PHASE3_DECISIONS P3-D7/D8).

Every workspace path is resolved (following symlinks) and must live inside the
project's workspace root. Absolute paths, ``..`` traversal, and symlink escapes
are rejected. A deny-list hides sensitive files entirely.
"""

from __future__ import annotations

import fnmatch
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchos.common.config import get_settings
from researchos.common.errors import AppError

# Sensitive file patterns (matched against the basename) and directory names
# (matched against any path component). Denied entries are never listed in the
# tree and return 403 on read/patch.
DENY_FILE_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "id_dsa*",
    "*credential*",
    "*credentials*",
    "*.secret",
    ".netrc",
    ".npmrc",
)
DENY_DIR_NAMES: frozenset[str] = frozenset({".git", ".ros-staging"})
_MOUNT_METADATA_DIR = ".researchos-mounts"
_MAX_RECENT_ROOTS = 8


class WorkspaceAccessError(AppError):
    code = "workspace_forbidden"
    http_status = 403
    message = "Access to this path is not allowed."


@dataclass(frozen=True)
class LocalWorkspaceSelection:
    root: Path
    default_root: Path
    uses_default: bool
    recent_roots: tuple[Path, ...]
    available: bool


def _workspace_base() -> Path:
    return Path(get_settings().workspace_root).expanduser().resolve()


def _default_workspace_root(project_id: uuid.UUID | str) -> Path:
    return _workspace_base() / str(project_id)


def _mount_metadata_path(project_id: uuid.UUID | str) -> Path:
    return _workspace_base() / _MOUNT_METADATA_DIR / f"{project_id}.json"


def _load_mount_metadata(project_id: uuid.UUID | str) -> dict[str, Any]:
    path = _mount_metadata_path(project_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get_local_workspace_selection(project_id: uuid.UUID | str) -> LocalWorkspaceSelection:
    """Return the persisted local folder selection for a project.

    The small pointer file lives outside every project workspace, so all
    existing filesystem, Git, patch and Agent code can resolve the same active
    root synchronously. A missing mounted directory is never recreated
    implicitly: the IDE reports it as unavailable and asks the user to choose
    another folder.
    """

    default_root = _default_workspace_root(project_id)
    data = _load_mount_metadata(project_id)
    active = data.get("active_root")
    uses_default = not isinstance(active, str) or not active.strip()
    root = default_root if uses_default else Path(active).expanduser()

    recent: list[Path] = []
    raw_recent = data.get("recent_roots", [])
    if isinstance(raw_recent, list):
        for value in raw_recent:
            if not isinstance(value, str) or not value.strip():
                continue
            candidate = Path(value).expanduser()
            if candidate not in recent:
                recent.append(candidate)

    return LocalWorkspaceSelection(
        root=root,
        default_root=default_root,
        uses_default=uses_default,
        recent_roots=tuple(recent[:_MAX_RECENT_ROOTS]),
        available=uses_default or (root.exists() and root.is_dir()),
    )


def validate_local_workspace_root(value: str) -> Path:
    """Validate an explicit host path before it can become an IDE root."""

    settings = get_settings()
    if settings.environment != "local":
        raise WorkspaceAccessError(
            "Custom local folders are available only when the API runs in local mode."
        )

    candidate = Path(value.strip()).expanduser()
    if not candidate.is_absolute():
        raise WorkspaceAccessError("The local workspace path must be absolute.")
    try:
        candidate = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise WorkspaceAccessError("The selected local folder does not exist.") from exc
    if not candidate.is_dir():
        raise WorkspaceAccessError("The selected local workspace must be a directory.")
    if candidate.parent == candidate:
        raise WorkspaceAccessError("A filesystem root cannot be used as a workspace.")

    home = Path.home().resolve()
    if candidate == home:
        raise WorkspaceAccessError("The home directory itself cannot be used as a workspace.")

    managed_base = _workspace_base()
    try:
        inside_managed_base = candidate.is_relative_to(managed_base)
    except ValueError:
        inside_managed_base = False
    if candidate == managed_base or inside_managed_base:
        raise WorkspaceAccessError(
            "Managed ResearchOS storage cannot be mounted as a custom workspace. "
            "Use the managed workspace option instead."
        )
    return candidate


def set_local_workspace_root(project_id: uuid.UUID | str, root: Path) -> None:
    """Atomically persist a validated active root and bounded recent history."""

    current = get_local_workspace_selection(project_id)
    recent = [root, *(item for item in current.recent_roots if item != root)]
    _write_mount_metadata(
        project_id,
        {
            "version": 1,
            "active_root": str(root),
            "recent_roots": [str(item) for item in recent[:_MAX_RECENT_ROOTS]],
        },
    )


def reset_local_workspace_root(project_id: uuid.UUID | str) -> None:
    """Switch back to the isolated ResearchOS-managed project directory."""

    current = get_local_workspace_selection(project_id)
    _write_mount_metadata(
        project_id,
        {
            "version": 1,
            "active_root": None,
            "recent_roots": [str(item) for item in current.recent_roots],
        },
    )


def _write_mount_metadata(project_id: uuid.UUID | str, data: dict[str, Any]) -> None:
    target = _mount_metadata_path(project_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def workspace_root_for(project_id: uuid.UUID | str) -> Path:
    selection = get_local_workspace_selection(project_id)
    if not selection.available:
        raise WorkspaceAccessError(
            "The selected local workspace is unavailable. Choose another folder or reset "
            "to the managed workspace."
        )
    return selection.root


def is_denied(relpath: str) -> bool:
    """Whether a workspace-relative path is on the deny-list."""

    parts = [p for p in relpath.replace("\\", "/").split("/") if p]
    if any(part in DENY_DIR_NAMES for part in parts):
        return True
    name = parts[-1] if parts else ""
    return any(fnmatch.fnmatch(name, pat) for pat in DENY_FILE_GLOBS)


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        return candidate.is_relative_to(root)
    except ValueError:
        return False


def resolve_in_workspace(project_id: uuid.UUID | str, user_path: str) -> Path:
    """Resolve ``user_path`` within the project workspace or raise 403.

    Rejects empty paths, absolute paths, ``..`` escapes, symlink escapes, and
    deny-listed files.
    """

    if not user_path or not user_path.strip():
        raise WorkspaceAccessError("A path is required.")

    root = workspace_root_for(project_id).resolve()
    candidate = (root / user_path).resolve()

    if not _is_within(candidate, root):
        raise WorkspaceAccessError("Path escapes the workspace root.")

    rel = candidate.relative_to(root).as_posix()
    if is_denied(rel):
        raise WorkspaceAccessError("This file is protected and cannot be accessed.")

    return candidate


def relative_to_root(project_id: uuid.UUID | str, path: Path) -> str:
    root = workspace_root_for(project_id).resolve()
    return path.resolve().relative_to(root).as_posix()
