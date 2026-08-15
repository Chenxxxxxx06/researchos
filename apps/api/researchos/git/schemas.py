"""Git DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    repository_snapshot_id: uuid.UUID | None = None
    source_commit_sha: str | None = None


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


class ImportRepositoryRequest(BaseModel):
    idea_id: uuid.UUID
    github_url: str = Field(min_length=20, max_length=1024)
    approved: Literal[True]


class RepositorySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    idea_id: uuid.UUID
    approved_by: uuid.UUID
    source_url: str
    source_owner: str
    source_repo: str
    destination_path: str
    status: str
    commit_sha: str | None
    default_branch: str | None
    license_spdx: str | None
    license_path: str | None
    file_count: int
    total_bytes: int
    skipped_files_json: list
    submodules_json: list
    manifest_hash: str | None
    workspace_commit_sha: str | None
    coding_session_id: uuid.UUID | None
    coding_run_id: uuid.UUID | None
    imported_at: datetime | None
    error: str | None
    created_at: datetime


class StartRepositoryCodingResponse(BaseModel):
    snapshot_id: uuid.UUID
    coding_session_id: uuid.UUID
    coding_run_id: uuid.UUID
    stream: str
