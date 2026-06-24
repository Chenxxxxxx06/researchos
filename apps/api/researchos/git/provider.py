"""Git status providers (read-only).

MVP ships a stub that always reports a clean workspace. A read-only provider
interface is reserved for a future phase, but no destructive git operations are
ever performed (PHASE3-D10).
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from .schemas import GitStatusResponse


@runtime_checkable
class GitStatusProvider(Protocol):
    name: str

    def status(self, project_id: uuid.UUID) -> GitStatusResponse: ...


class StubGitStatusProvider:
    """Always reports a clean, single-branch repository."""

    name = "stub"

    def status(self, project_id: uuid.UUID) -> GitStatusResponse:
        return GitStatusResponse(provider=self.name, branch="main", clean=True, files=[])


class ReadOnlyGitStatusProvider:
    """Reserved interface for a future read-only ``git status --porcelain`` impl.

    Intentionally not implemented in Phase 3.
    """

    name = "readonly-git"

    def status(self, project_id: uuid.UUID) -> GitStatusResponse:  # pragma: no cover
        raise NotImplementedError("Read-only git provider is not implemented in Phase 3.")


def get_git_provider() -> GitStatusProvider:
    return StubGitStatusProvider()
