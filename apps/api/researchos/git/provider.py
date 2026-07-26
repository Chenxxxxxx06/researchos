"""Git status providers.

``RealGitStatusProvider`` parses ``git status --porcelain=v1 --branch``;
``DisabledGitStatusProvider`` is the degradation when the git binary is absent
or ``GIT_ENABLED=false``. Status is a read path: it never initializes a repo
(an uninitialized workspace reports pristine).
"""

from __future__ import annotations

import re
import uuid
from typing import Protocol, runtime_checkable

from researchos.common.paths import workspace_root_for

from .runner import git_available, run_git
from .schemas import GitFileState, GitFileStatus, GitStatusResponse

_AHEAD_RE = re.compile(r"ahead (\d+)")
_BEHIND_RE = re.compile(r"behind (\d+)")

_XY_STATES: dict[str, GitFileState] = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
}


@runtime_checkable
class GitStatusProvider(Protocol):
    name: str

    def status(self, project_id: uuid.UUID) -> GitStatusResponse: ...


def _parse_branch_header(header: str) -> tuple[str, int, int]:
    """Parse the ``## ...`` line of porcelain v1 --branch output."""

    body = header[3:].strip()
    ahead = behind = 0
    if body.startswith("No commits yet on "):
        return body[len("No commits yet on ") :].strip(), ahead, behind
    if body.startswith("HEAD "):  # detached: "HEAD (no branch)"
        return "HEAD", ahead, behind
    bracket = ""
    if "[" in body:
        body, _, bracket = body.partition("[")
    branch = body.split("...", 1)[0].strip()
    if bracket:
        m = _AHEAD_RE.search(bracket)
        ahead = int(m.group(1)) if m else 0
        m = _BEHIND_RE.search(bracket)
        behind = int(m.group(1)) if m else 0
    return branch, ahead, behind


def parse_porcelain_status(output: str) -> tuple[str, int, int, list[GitFileStatus]]:
    """Pure porcelain v1 parser (unit-testable without a git binary)."""

    branch = "main"
    ahead = behind = 0
    files: list[GitFileStatus] = []
    for line in output.splitlines():
        if not line:
            continue
        if line.startswith("## "):
            branch, ahead, behind = _parse_branch_header(line)
            continue
        if len(line) < 4:
            continue
        xy, rest = line[:2], line[3:]
        if xy == "??":
            files.append(GitFileStatus(path=rest, state="untracked"))
            continue
        state: GitFileState | None = None
        for ch in xy:
            if ch in _XY_STATES:
                state = _XY_STATES[ch]
                break
        if state is None:
            continue
        path = rest
        if state == "renamed" and " -> " in rest:
            path = rest.split(" -> ", 1)[1]
        files.append(GitFileStatus(path=path, state=state))
    return branch, ahead, behind, files


class RealGitStatusProvider:
    """Reads real repository state via ``git status --porcelain=v1``."""

    name = "git"

    def status(self, project_id: uuid.UUID) -> GitStatusResponse:
        root = workspace_root_for(project_id)
        if not (root / ".git").exists():
            # Read path stays side-effect free: no lazy init here.
            return GitStatusResponse(provider=self.name, branch="main", clean=True, files=[])
        proc = run_git(
            root, "status", "--porcelain=v1", "--branch", "--untracked-files=all"
        )
        branch, ahead, behind, files = parse_porcelain_status(proc.stdout)
        return GitStatusResponse(
            provider=self.name,
            branch=branch,
            clean=not files,
            ahead=ahead,
            behind=behind,
            files=files,
        )


class DisabledGitStatusProvider:
    """Degradation when git is disabled or the binary is missing."""

    name = "disabled"

    def status(self, project_id: uuid.UUID) -> GitStatusResponse:
        return GitStatusResponse(provider=self.name, branch="", clean=True, files=[])


def get_git_provider() -> GitStatusProvider:
    return RealGitStatusProvider() if git_available() else DisabledGitStatusProvider()
