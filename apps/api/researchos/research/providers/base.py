"""Paper search provider protocol and normalized result DTO.

A ``PaperResult`` always preserves the source and external identifier so that
everything shown by Research Copilot is traceable and citations cannot be
fabricated.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchos.common.errors import AppError

SortOrder = Literal["relevance", "latest"]

# arXiv-style category slugs: "cs.LG", "stat.ML", "math-ph", "solv-int".
CATEGORY_RE = re.compile(r"^[a-z-]+(\.[A-Za-z-]+)?$")


class ProviderError(AppError):
    code = "provider_error"
    http_status = 502
    message = "The paper search provider is unavailable."


class PaperSearchFilters(BaseModel):
    # Kept for backward compatibility; mapped onto the date window when no
    # explicit date_from/date_to is given.
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    categories: list[str] = Field(default_factory=list, max_length=8)
    date_from: date | None = None
    date_to: date | None = None
    author: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    abstract: str | None = Field(default=None, max_length=300)
    sort: SortOrder = "relevance"
    offset: int = Field(default=0, ge=0, le=1000)

    @field_validator("categories")
    @classmethod
    def _validate_categories(cls, value: list[str]) -> list[str]:
        for category in value:
            if not CATEGORY_RE.match(category):
                raise ValueError(f"Invalid category: {category!r}")
        return value

    def date_window(self) -> tuple[date | None, date | None]:
        """Effective (from, to) dates, with year_from/year_to as fallbacks."""

        start = self.date_from
        if start is None and self.year_from is not None:
            start = date(self.year_from, 1, 1)
        end = self.date_to
        if end is None and self.year_to is not None:
            end = date(self.year_to, 12, 31)
        return start, end

    def has_fielded_terms(self) -> bool:
        return bool(self.categories or self.author or self.title or self.abstract)


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
    doi: str | None = None
    citation_count: int | None = None
    categories: list[str] = Field(default_factory=list)
    # Original provider fields preserved for traceability.
    extra: dict = Field(default_factory=dict)

    @property
    def citation_key(self) -> str:
        return f"{self.source}:{self.external_id}"


class PaperImportRef(BaseModel):
    """Reference-only import item; every other client-supplied field is ignored.

    The server re-fetches authoritative metadata by ``(source, external_id)``
    so fabricated paper payloads can never enter the library.
    """

    model_config = ConfigDict(extra="ignore")

    source: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=255)


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

    async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]: ...
