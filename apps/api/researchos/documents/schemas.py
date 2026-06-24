"""LaTeX document DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import CompileStatus


class CreateLatexProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class LatexProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    main_file_path: str
    created_at: datetime


class DocumentFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    content: str
    version: int
    updated_at: datetime


class DocumentFileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    version: int


class SaveFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(default="", max_length=2_000_000)


class CompileJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    latex_project_id: uuid.UUID
    status: CompileStatus
    engine: str
    log: str | None
    preview: str | None
    error_summary: str | None
    created_at: datetime
    finished_at: datetime | None
