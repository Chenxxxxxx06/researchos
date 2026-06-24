"""Workspace path guard (see PHASE3_DECISIONS P3-D7/D8).

Every workspace path is resolved (following symlinks) and must live inside the
project's workspace root. Absolute paths, ``..`` traversal, and symlink escapes
are rejected. A deny-list hides sensitive files entirely.
"""

from __future__ import annotations

import fnmatch
import uuid
from pathlib import Path

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
DENY_DIR_NAMES: frozenset[str] = frozenset({".git"})


class WorkspaceAccessError(AppError):
    code = "workspace_forbidden"
    http_status = 403
    message = "Access to this path is not allowed."


def workspace_root_for(project_id: uuid.UUID | str) -> Path:
    return Path(get_settings().workspace_root) / str(project_id)


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
