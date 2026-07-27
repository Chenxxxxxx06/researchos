"""Subprocess git runner (feature-flagged, injection-safe).

All git access goes through ``run_git``: argv exec only (never a shell),
prompts disabled, timeouts enforced. User-supplied shas must be validated with
``validate_sha`` and user-supplied paths must pass ``resolve_in_workspace``
before reaching a git call site (and are passed after a literal ``--``).
No destructive history operations exist anywhere (P3-D10 core retained).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from researchos.common.config import get_settings
from researchos.common.errors import AppError, ValidationError

_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")


class GitError(AppError):
    code = "git_error"
    http_status = 500
    message = "Git operation failed."


class GitDisabled(AppError):
    code = "git_disabled"
    http_status = 409
    message = "Git is not available in this deployment."


@lru_cache(maxsize=1)
def git_available() -> bool:
    """Whether git is enabled by config and the binary exists on PATH."""

    return bool(get_settings().git_enabled and shutil.which("git"))


def validate_sha(sha: str) -> str:
    if not _SHA_RE.match(sha or ""):
        raise ValidationError("Invalid commit sha.")
    return sha


def run_git(
    root: Path,
    *args: str,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    settings = get_settings()
    # Provide fallback identity via env so git commit never needs config files
    # (CI runners may lack ~/.gitconfig and /etc/gitconfig).
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME", "ResearchOS"),
        "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL", "bot@researchos.local"),
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME", "ResearchOS"),
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL", "bot@researchos.local"),
    }
    try:
        proc = subprocess.run(  # noqa: S603 - argv exec, no shell; inputs validated upstream
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or settings.git_timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {args[0] if args else ''} timed out.") from exc
    except OSError as exc:
        raise GitError(f"git could not be executed: {exc}") from exc
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "").strip()[:500]
        raise GitError(f"git {args[0] if args else ''} failed: {stderr}")
    return proc
