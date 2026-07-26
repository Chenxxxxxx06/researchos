"""Git DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

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


class GitCommitEntry(BaseModel):
    sha: str
    author_name: str
    author_email: str
    authored_at: datetime
    summary: str
    patch_id: uuid.UUID | None = None
    agent_run_id: uuid.UUID | None = None
    reverts_sha: str | None = None


class GitLogResponse(BaseModel):
    entries: list[GitCommitEntry]


class GitCommitDiffFile(BaseModel):
    path: str
    change_type: Literal["added", "modified", "deleted", "renamed"]
    old_path: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    omitted: bool = False
    size: int = 0


class GitCommitDiff(BaseModel):
    sha: str
    summary: str
    author_name: str
    authored_at: datetime
    files: list[GitCommitDiffFile]


class GitRevertRequest(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{7,64}$")


class GitRevertResponse(BaseModel):
    commit_sha: str
    reverted_sha: str
