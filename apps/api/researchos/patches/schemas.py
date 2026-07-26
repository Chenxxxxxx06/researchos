"""Patch proposal DTOs.

Hunks are server-derived only (clients can no longer submit them); ``modify``
requires ``base_sha`` at the schema boundary, which closes the historical
``None == None`` conflict-scan hole.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import PatchChangeType, PatchStatus


# --- inputs ------------------------------------------------------------------
class PatchEditInput(BaseModel):
    search: str = Field(min_length=1)
    replace: str


class PatchFileInput(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    change_type: PatchChangeType
    base_sha: str | None = None
    new_content: str | None = None
    edits: list[PatchEditInput] | None = None

    @model_validator(mode="after")
    def _validate_change_shape(self) -> PatchFileInput:
        if self.change_type == PatchChangeType.CREATE:
            if self.new_content is None:
                raise ValueError("create requires new_content")
            if self.edits:
                raise ValueError("create cannot carry edits")
            if self.base_sha is not None:
                raise ValueError("create cannot carry base_sha")
        elif self.change_type == PatchChangeType.MODIFY:
            if self.base_sha is None:
                raise ValueError("modify requires base_sha")
            has_content = self.new_content is not None
            has_edits = bool(self.edits)
            if has_content == has_edits:
                raise ValueError("modify requires exactly one of new_content or edits")
        else:  # DELETE
            if self.new_content is not None or self.edits:
                raise ValueError("delete cannot carry new_content or edits")
        return self


class CreatePatchRequest(BaseModel):
    summary: str = Field(default="", max_length=2000)
    files: list[PatchFileInput] = Field(min_length=1, max_length=100)


class ApplyPatchRequest(BaseModel):
    """Optional apply body: restrict the apply to a subset of file paths."""

    paths: list[str] | None = Field(default=None, min_length=1)


# --- responses ---------------------------------------------------------------
class PatchEditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    search: str
    replace: str


class PatchHunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str


class PatchFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    change_type: PatchChangeType
    base_sha: str | None
    new_content: str | None
    base_content: str | None = None
    edits: list[PatchEditResponse] = []
    hunks: list[PatchHunkResponse] = []


class PatchConflict(BaseModel):
    path: str
    expected_sha: str | None
    actual_sha: str | None
    reason: str


class PatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    created_by: uuid.UUID
    status: PatchStatus
    summary: str
    created_at: datetime
    applied_at: datetime | None
    applied_commit_sha: str | None = None
    conflicts: list[PatchConflict] = []
    superseded_by: uuid.UUID | None = None
    files: list[PatchFileResponse] = []


class ApplyResultResponse(BaseModel):
    patch_id: uuid.UUID
    status: PatchStatus
    conflicts: list[PatchConflict] = []
    applied_commit_sha: str | None = None
    skipped_paths: list[str] = []
