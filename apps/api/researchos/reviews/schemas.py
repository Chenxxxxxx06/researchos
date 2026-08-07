"""Review document API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateReviewOutlineRequest(BaseModel):
    regenerate: bool = False


class GenerateReviewSectionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    regenerate: bool = False


class UpdateReviewSectionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    purpose: str | None = Field(default=None, max_length=10_000)
    body: str | None = Field(default=None, max_length=100_000)
    citations: list[uuid.UUID] | None = Field(default=None, max_length=500)
    claims: list[dict] | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(outline|draft|needs_review|approved)$")


class ReviewSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    section_key: str
    position: int
    title: str
    purpose: str
    body: str
    citations_json: list
    claims_json: list
    status: str
    version: int
    generated_by_run_id: uuid.UUID | None
    updated_at: datetime


class ReviewDocumentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    title: str
    status: str
    version: int
    citation_coverage: float
    unsupported_claims: int
    sections: list[ReviewSectionResponse]
    created_at: datetime
    updated_at: datetime


class ReviewVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    review_id: uuid.UUID
    version: int
    snapshot_json: dict
    source_type: str
    source_run_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
