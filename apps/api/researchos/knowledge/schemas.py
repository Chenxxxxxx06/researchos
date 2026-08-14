"""API contracts for mission knowledge artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from researchos.research.enums import PaperIngestStatus, PaperSectionKind


class AddMissionPapersRequest(BaseModel):
    paper_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    inclusion_reason: str = Field(default="", max_length=4000)


class MissionPaperResponse(BaseModel):
    id: uuid.UUID
    paper_id: uuid.UUID
    cluster_id: uuid.UUID | None
    relevance_score: float | None
    inclusion_reason: str
    title: str
    authors: list
    venue: str | None
    published_at: datetime | None
    ingest_status: PaperIngestStatus


class TopicClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    mission_id: uuid.UUID
    name: str
    summary: str
    keywords_json: list
    algorithm: str
    status: str
    position: int
    version: int
    created_at: datetime
    updated_at: datetime
    paper_count: int = 0


class UpdateTopicClusterRequest(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=10_000)
    keywords: list[str] | None = Field(default=None, max_length=50)


class ReadingCardUpsertRequest(BaseModel):
    mission_id: uuid.UUID
    expected_version: int | None = Field(default=None, ge=1)
    summary: str = Field(default="", max_length=30_000)
    research_question: str = Field(default="", max_length=10_000)
    method_flow: list[str] = Field(default_factory=list, max_length=100)
    strengths: list[str] = Field(default_factory=list, max_length=100)
    limitations: list[str] = Field(default_factory=list, max_length=100)
    reproducibility: list[str] = Field(default_factory=list, max_length=100)
    claims: list[dict] = Field(default_factory=list, max_length=200)
    status: str = Field(default="draft", pattern="^(draft|needs_review|reviewed)$")


class ReadingCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    paper_id: uuid.UUID
    summary: str
    research_question: str
    method_flow_json: list
    strengths_json: list
    limitations_json: list
    reproducibility_json: list
    claims_json: list
    status: str
    version: int
    generated_by_run_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReadingCardVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    card_id: uuid.UUID
    mission_id: uuid.UUID
    paper_id: uuid.UUID
    version: int
    snapshot_json: dict
    source_type: str
    source_run_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


class GenerateReadingCardRequest(BaseModel):
    mission_id: uuid.UUID
    regenerate: bool = False


class ReadingNoteCreateRequest(BaseModel):
    mission_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    quote: str = Field(default="", max_length=20_000)
    content: str = Field(min_length=1, max_length=30_000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class ReadingNoteUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    quote: str | None = Field(default=None, max_length=20_000)
    content: str | None = Field(default=None, min_length=1, max_length=30_000)
    tags: list[str] | None = Field(default=None, max_length=30)


class ReadingNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID | None
    paper_id: uuid.UUID
    section_id: uuid.UUID | None
    quote: str
    content: str
    tags_json: list
    version: int
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    mission_id: uuid.UUID | None = None
    limit: int = Field(default=12, ge=1, le=50)
    kinds: list[PaperSectionKind] = Field(default_factory=list)


class RagHitResponse(BaseModel):
    chunk_id: uuid.UUID | None = None
    paper_id: uuid.UUID
    section_id: uuid.UUID | None
    title: str
    heading: str
    kind: PaperSectionKind | None
    snippet: str
    score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    citation_key: str


class RagSearchResponse(BaseModel):
    query: str
    mode: str
    embedding_model: str
    indexed_papers: int = 0
    indexed_chunks: int = 0
    hits: list[RagHitResponse]
