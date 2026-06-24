"""Paper search provider protocol and normalized result DTO.

A ``PaperResult`` always preserves the source and external identifier so that
everything shown by Research Copilot is traceable and citations cannot be
fabricated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class PaperSearchFilters(BaseModel):
    year_from: int | None = None
    year_to: int | None = None


class PaperResult(BaseModel):
    source: str
    external_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    published_at: datetime | None = None
    url: str
    pdf_url: str | None = None
    # Original provider fields preserved for traceability.
    extra: dict = Field(default_factory=dict)

    @property
    def citation_key(self) -> str:
        return f"{self.source}:{self.external_id}"


@runtime_checkable
class PaperSearchProvider(Protocol):
    name: str

    async def search(
        self,
        query: str,
        *,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]: ...
