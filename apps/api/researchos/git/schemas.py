"""Git status DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GitFileState = Literal["modified", "added", "deleted", "untracked", "renamed"]


class GitFileStatus(BaseModel):
    path: str
    state: GitFileState


class GitStatusResponse(BaseModel):
    provider: str
    branch: str
    clean: bool
    ahead: int = 0
    behind: int = 0
    files: list[GitFileStatus] = []
