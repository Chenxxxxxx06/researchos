"""Patch proposal DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import PatchChangeType, PatchStatus


# --- inputs ------------------------------------------------------------------
class PatchHunkInput(BaseModel):
    header: str = ""
    old_start: int = 0
    old_lines: int = 0
    new_start: int = 0
    new_lines: int = 0
    content: str = ""


class PatchFileInput(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    change_type: PatchChangeType
    base_sha: str | None = None
    new_content: str | None = None
    hunks: list[PatchHunkInput] = Field(default_factory=list)


class CreatePatchRequest(BaseModel):
    summary: str = Field(default="", max_length=2000)
    files: list[PatchFileInput] = Field(min_length=1, max_length=100)


# --- responses ---------------------------------------------------------------
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
    hunks: list[PatchHunkResponse] = []


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
    files: list[PatchFileResponse] = []


class PatchConflict(BaseModel):
    path: str
    expected_sha: str | None
    actual_sha: str | None
    reason: str


class ApplyResultResponse(BaseModel):
    patch_id: uuid.UUID
    status: PatchStatus
    conflicts: list[PatchConflict] = []
