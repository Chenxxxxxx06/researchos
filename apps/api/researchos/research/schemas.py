"""Research DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from researchos.research.providers.base import (
    CATEGORY_RE,
    PaperImportRef,
    PaperResult,
    PaperSearchFilters,
)

from .enums import IdeaStatus, PaperIngestStatus, PaperSectionKind


# --- Papers ------------------------------------------------------------------
class PaperSearchRequest(BaseModel):
    # Empty query is allowed iff filters carry categories or fielded terms.
    query: str = Field(default="", max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    filters: PaperSearchFilters | None = None

    @model_validator(mode="after")
    def _query_or_fielded_filters(self) -> PaperSearchRequest:
        if self.query.strip():
            return self
        if self.filters is not None and self.filters.has_fielded_terms():
            return self
        raise ValueError(
            "query must be non-empty unless filters provide categories or fielded terms"
        )


class PaperSearchResponse(BaseModel):
    results: list[PaperResult]
    provider_status: dict[str, str] = Field(default_factory=dict)


class ImportPapersRequest(BaseModel):
    papers: list[PaperImportRef] = Field(min_length=1, max_length=50)


SkipReason = Literal["not_found", "provider_error", "invalid_source"]


class SkippedImport(BaseModel):
    source: str
    external_id: str
    reason: SkipReason


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
    doi: str | None = None
    arxiv_id: str | None = None
    primary_category: str | None = None
    citation_count: int | None = None
    ingest_status: PaperIngestStatus = PaperIngestStatus.PENDING
    ingested_at: datetime | None = None
    created_at: datetime


class ImportPapersResponse(BaseModel):
    imported: list[PaperResponse]
    skipped: list[SkippedImport] = Field(default_factory=list)


# --- Paper references (delete preflight) --------------------------------------
class PaperReferenceCounts(BaseModel):
    """How many downstream artifacts reference a paper, per category."""

    reading_cards: int = 0
    reading_notes: int = 0
    review_sections: int = 0
    experiment_plans: int = 0
    missions: int = 0


class PaperReferencesResponse(BaseModel):
    paper_id: uuid.UUID
    references: PaperReferenceCounts
    blocked: bool


# --- Paper sections ----------------------------------------------------------
class PaperSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    level: int
    kind: PaperSectionKind
    heading: str
    body: str
    char_count: int


class SectionsResponse(BaseModel):
    paper_id: uuid.UUID
    ingest_status: PaperIngestStatus
    ingested_at: datetime | None
    ingest_error: str | None
    sections: list[PaperSectionResponse]


class IngestTriggerResponse(BaseModel):
    paper_id: uuid.UUID
    ingest_status: PaperIngestStatus


# --- Freshness feed ----------------------------------------------------------
class FeedItem(PaperResult):
    in_library: bool = False


class FeedResponse(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None = None
    categories_used: list[str] = Field(default_factory=list)
    cached: bool = False


class FeedCategoriesRequest(BaseModel):
    categories: list[str] = Field(min_length=0, max_length=8)

    @field_validator("categories")
    @classmethod
    def _validate_categories(cls, value: list[str]) -> list[str]:
        for category in value:
            if not CATEGORY_RE.match(category):
                raise ValueError(f"Invalid category: {category!r}")
        return value


class FeedCategoriesResponse(BaseModel):
    categories: list[str]
    derived: bool


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
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    hypothesis: str | None
    status: IdeaStatus
    novelty_score: float | None
    # Gap-generation fields (gap_type, supporting_paper_keys, ...) live here.
    metadata: dict = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata_json", "metadata"),
    )
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class GenerateIdeasRequest(BaseModel):
    max_ideas: int = Field(default=3, ge=1, le=5)


class GenerateIdeasResponse(BaseModel):
    ideas: list[IdeaResponse]
    gaps_considered: int
    papers_used: int


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
