"""Research DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from researchos.research.providers.base import PaperResult

from .enums import IdeaStatus


# --- Papers ------------------------------------------------------------------
class PaperSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class PaperSearchResponse(BaseModel):
    results: list[PaperResult]


class ImportPapersRequest(BaseModel):
    papers: list[PaperResult] = Field(min_length=1, max_length=50)


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source: str
    external_id: str
    title: str
    abstract: str | None
    authors_json: list
    venue: str | None
    published_at: datetime | None
    url: str
    pdf_url: str | None
    summary: str | None
    created_at: datetime


# --- Ideas -------------------------------------------------------------------
class CreateIdeaRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20_000)
    hypothesis: str | None = Field(default=None, max_length=20_000)


class UpdateIdeaRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    hypothesis: str | None = Field(default=None, max_length=20_000)
    status: IdeaStatus | None = None


class IdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    hypothesis: str | None
    status: IdeaStatus
    novelty_score: float | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Critiques ---------------------------------------------------------------
class CritiqueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    idea_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    novelty_summary: str
    weaknesses_json: list
    missing_baselines_json: list
    dataset_risks_json: list
    reproducibility_json: list
    citations_json: list
    created_at: datetime
