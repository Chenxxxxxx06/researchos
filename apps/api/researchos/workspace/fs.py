"""Low-level controlled filesystem access for project workspaces.

All access goes through the path guard in ``researchos.common.paths``. The
filesystem is the source of truth for content and the tree (PHASE3-D2); nothing
here is cached in the database. I/O is synchronous (small files; P3-D14).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.hashing import sha256_hex
from researchos.common.paths import (
    is_denied,
    resolve_in_workspace,
    workspace_root_for,
)


def ensure_workspace(project_id: uuid.UUID) -> Path:
    root = workspace_root_for(project_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_dir(node: Path, root: Path, rel: str, depth: int, counter: list[int]) -> list[dict]:
    settings = get_settings()
    if depth > settings.workspace_max_tree_depth:
        return []
    children: list[dict] = []
    try:
        entries = sorted(node.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return []
    for entry in entries:
        if counter[0] >= settings.workspace_max_tree_entries:
            break
        child_rel = f"{rel}/{entry.name}" if rel else entry.name
        if is_denied(child_rel):
            continue
        # Skip symlinks that escape the workspace root (defense in depth).
        if entry.is_symlink():
            try:
                if not entry.resolve().is_relative_to(root):
                    continue
            except (ValueError, OSError):
                continue
        counter[0] += 1
        if entry.is_dir():
            children.append(
                {
                    "name": entry.name,
                    "path": child_rel,
                    "type": "dir",
                    "children": _build_dir(entry, root, child_rel, depth + 1, counter),
                }
            )
        else:
            children.append({"name": entry.name, "path": child_rel, "type": "file"})
    return children


def build_tree(project_id: uuid.UUID) -> list[dict]:
    root = ensure_workspace(project_id).resolve()
    counter = [0]
    return _build_dir(root, root, "", 0, counter)


def read_file(project_id: uuid.UUID, path: str) -> dict:
    resolved = resolve_in_workspace(project_id, path)
    if not resolved.exists():
        raise NotFoundError("File not found.")
    if resolved.is_dir():
        raise ValidationError("Path is a directory, not a file.")

    settings = get_settings()
    size = resolved.stat().st_size
    if size > settings.workspace_max_file_bytes:
        return {
            "path": path,
            "binary": True,
            "size": size,
            "content": None,
            "sha": None,
            "too_large": True,
        }

    raw = resolved.read_bytes()
    if b"\x00" in raw[:8192]:
        return {
            "path": path,
            "binary": True,
            "size": size,
            "content": None,
            "sha": sha256_hex(raw),
            "too_large": False,
        }

    text = raw.decode("utf-8", errors="replace")
    return {
        "path": path,
        "binary": False,
        "size": size,
        "content": text,
        "sha": sha256_hex(raw),
        "too_large": False,
    }


def current_sha(project_id: uuid.UUID, path: str) -> str | None:
    resolved = resolve_in_workspace(project_id, path)
    if not resolved.exists() or resolved.is_dir():
        return None
    return sha256_hex(resolved.read_bytes())


def write_file(project_id: uuid.UUID, path: str, content: str) -> str:
    """Write a file (creating parent dirs). Returns the new sha. Patch-apply only."""

    resolved = resolve_in_workspace(project_id, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    resolved.write_bytes(data)
    return sha256_hex(data)


def delete_file(project_id: uuid.UUID, path: str) -> None:
    resolved = resolve_in_workspace(project_id, path)
    if resolved.exists() and resolved.is_file():
        resolved.unlink()
