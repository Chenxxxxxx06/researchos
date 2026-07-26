"""Low-level controlled filesystem access for project workspaces.

All access goes through the path guard in ``researchos.common.paths``. The
filesystem is the source of truth for content and the tree (PHASE3-D2); nothing
here is cached in the database. I/O is synchronous (small files; P3-D14).
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.hashing import sha256_hex
from researchos.common.paths import (
    is_denied,
    resolve_in_workspace,
    workspace_root_for,
)

logger = structlog.get_logger(__name__)

_STAGING_DIR_NAME = ".ros-staging"
_STAGING_MAX_AGE_SECONDS = 24 * 60 * 60
_GREP_MAX_FILES_SCANNED = 2000
_GREP_MAX_LINE_CHARS = 300


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


def read_file_range(
    project_id: uuid.UUID,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    max_lines: int | None = None,
) -> dict:
    """Read a 1-based inclusive line range of a text file.

    The ``sha`` is computed over the *whole* file regardless of the range so
    it can serve as the ``base_sha`` optimistic-concurrency guard. ``truncated``
    is set when the per-call line cap clamped the requested window.
    """

    data = read_file(project_id, path)
    if data["binary"] or data["too_large"]:
        return data

    cap = max_lines or get_settings().workspace_read_max_lines
    lines = (data["content"] or "").splitlines(keepends=True)
    total_lines = len(lines)

    start = max(1, int(start_line) if start_line else 1)
    end = int(end_line) if end_line else total_lines
    end = min(end, total_lines)
    truncated = False
    if end - start + 1 > cap:
        end = start + cap - 1
        truncated = True

    content = "".join(lines[start - 1 : end]) if end >= start else ""
    return {
        "path": path,
        "binary": False,
        "too_large": False,
        "size": data["size"],
        "content": content,
        "start_line": start,
        "end_line": end,
        "total_lines": total_lines,
        "sha": data["sha"],
        "truncated": truncated,
    }


def _resolves_inside(entry: Path, root: Path) -> bool:
    try:
        return entry.resolve().is_relative_to(root)
    except (ValueError, OSError):
        return False


def grep_files(
    project_id: uuid.UUID,
    pattern: str,
    *,
    glob: str | None = None,
    max_results: int = 50,
    ignore_case: bool = False,
) -> dict:
    """Bounded regex search across the workspace.

    Deterministic bounds: at most ``_GREP_MAX_FILES_SCANNED`` files scanned,
    oversized/binary files skipped, matched lines truncated to
    ``_GREP_MAX_LINE_CHARS`` chars, and at most ``max_results`` matches.
    Raises ``re.error`` for invalid patterns (callers map it to their surface).
    """

    compiled = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    settings = get_settings()
    root = ensure_workspace(project_id).resolve()

    matches: list[dict] = []
    files_scanned = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        # Prune denied directories (".git", ".ros-staging", ...) in place.
        dirnames[:] = sorted(
            d for d in dirnames if not is_denied(f"{rel_dir}/{d}" if rel_dir else d)
        )
        for name in sorted(filenames):
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if is_denied(rel):
                continue
            if glob and not fnmatch.fnmatch(rel, glob):
                continue
            if files_scanned >= _GREP_MAX_FILES_SCANNED:
                truncated = True
                break
            entry = Path(dirpath) / name
            if entry.is_symlink() and not _resolves_inside(entry, root):
                continue
            files_scanned += 1
            try:
                if entry.stat().st_size > settings.workspace_grep_max_file_bytes:
                    continue
                raw = entry.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:8192]:
                continue
            text = raw.decode("utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    matches.append(
                        {"path": rel, "line_no": line_no, "line": line[:_GREP_MAX_LINE_CHARS]}
                    )
                    if len(matches) >= max_results:
                        truncated = True
                        break
            if truncated:
                break
        if truncated:
            break

    return {"matches": matches, "truncated": truncated, "files_scanned": files_scanned}


# --- Atomic multi-file apply --------------------------------------------------
@dataclass(frozen=True)
class FileOp:
    path: str
    action: Literal["write", "delete"]
    content: str | None = None


class WorkspaceApplyError(Exception):
    """Atomic apply failed mid-commit. ``rolled_back`` reports recovery state."""

    def __init__(self, message: str, *, rolled_back: bool) -> None:
        self.rolled_back = rolled_back
        super().__init__(message)


def _cleanup_stale_staging(staging_root: Path) -> None:
    """Best-effort removal of staging dirs older than 24h (crashed applies)."""

    try:
        entries = list(staging_root.iterdir())
    except OSError:
        return
    cutoff = time.time() - _STAGING_MAX_AGE_SECONDS
    for entry in entries:
        try:
            if entry.is_dir() and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


def _fsync_dir(path: Path) -> None:
    # POSIX only; Windows cannot open directories for fsync.
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def apply_files_atomic(project_id: uuid.UUID, ops: list[FileOp]) -> dict[str, str]:
    """Apply write/delete ops atomically: stage + fsync, then journaled renames.

    Phase A touches nothing user-visible; any failure there leaves the
    workspace untouched. Phase B moves originals aside (restorable
    byte-identically) before placing staged files; on any failure the journal
    is unwound in reverse and ``WorkspaceApplyError(rolled_back=...)`` raised.
    Returns ``{path: sha256}`` for the written files.
    """

    root = ensure_workspace(project_id).resolve()
    staging_root = root / _STAGING_DIR_NAME
    staging_root.mkdir(exist_ok=True)
    _cleanup_stale_staging(staging_root)
    staging = staging_root / uuid.uuid4().hex
    staging.mkdir()

    # Phase A: guard every target and durably stage every write.
    resolved: list[tuple[int, FileOp, Path]] = []
    try:
        for i, op in enumerate(ops):
            target = resolve_in_workspace(project_id, op.path)
            resolved.append((i, op, target))
            if op.action == "write":
                stage = staging / f"stage-{i}"
                with open(stage, "wb") as fh:
                    fh.write((op.content or "").encode("utf-8"))
                    fh.flush()
                    os.fsync(fh.fileno())
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    # Phase B: journaled renames. Each entry records how to undo one step.
    journal: list[tuple[str, Path, Path]] = []  # (kind, src_now, restore_to)
    try:
        for i, op, target in resolved:
            if target.exists():
                backup = staging / f"backup-{i}"
                os.replace(target, backup)
                journal.append(("backup", backup, target))
            if op.action == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / f"stage-{i}", target)
                journal.append(("placed", target, staging / f"stage-{i}"))
    except Exception as exc:
        rolled_back = True
        for kind, src, dst in reversed(journal):
            try:
                if kind == "placed":
                    os.replace(src, dst)  # move the placed file back to staging
                else:
                    os.replace(src, dst)  # restore the original from backup
            except OSError:
                rolled_back = False
                logger.critical(
                    "workspace_apply_rollback_step_failed",
                    project_id=str(project_id),
                    kind=kind,
                    path=str(dst),
                )
        if rolled_back:
            shutil.rmtree(staging, ignore_errors=True)
        raise WorkspaceApplyError(str(exc), rolled_back=rolled_back) from exc

    for _, _op, target in resolved:
        _fsync_dir(target.parent)
    shutil.rmtree(staging, ignore_errors=True)
    return {
        op.path: sha256_hex((op.content or "").encode("utf-8"))
        for _, op, _t in resolved
        if op.action == "write"
    }
