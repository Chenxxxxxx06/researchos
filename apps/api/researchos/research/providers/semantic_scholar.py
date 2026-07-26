"""Semantic Scholar Graph API provider (keyless tier).

One request per search call; 429s are retried with backoff. The HTTP client is
injectable for tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from researchos.common.config import get_settings

from .base import PaperResult, PaperSearchFilters, ProviderError
from .retry import fetch_with_retry

logger = structlog.get_logger(__name__)

_FIELDS = (
    "title,abstract,externalIds,year,venue,citationCount,openAccessPdf,"
    "authors,publicationDate,url"
)


def _parse_date(value: str | None, year: int | None) -> datetime | None:
    if value:
        try:
            return datetime.fromisoformat(value).replace(tzinfo=UTC)
        except ValueError:
            pass
    if year:
        return datetime(year, 1, 1, tzinfo=UTC)
    return None


def _item_to_result(item: dict) -> PaperResult:
    paper_id = str(item.get("paperId", ""))
    external_ids = item.get("externalIds") or {}
    doi = external_ids.get("DOI")
    open_access = item.get("openAccessPdf") or {}
    extra: dict = {}
    arxiv_id = external_ids.get("ArXiv")
    if arxiv_id:
        extra["arxiv_id"] = arxiv_id
    return PaperResult(
        source="s2",
        external_id=paper_id,
        title=item.get("title") or "",
        abstract=item.get("abstract") or None,
        authors=[a.get("name", "") for a in item.get("authors") or []],
        venue=item.get("venue") or None,
        published_at=_parse_date(item.get("publicationDate"), item.get("year")),
        url=item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
        pdf_url=open_access.get("url"),
        doi=doi.lower() if isinstance(doi, str) and doi else None,
        citation_count=item.get("citationCount"),
        extra=extra,
    )


class SemanticScholarProvider:
    name = "s2"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        *,
        retry_base_delay: float = 0.5,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = (base_url or settings.s2_api_base).rstrip("/")
        self._timeout = settings.provider_timeout_seconds
        self._retry_attempts = settings.provider_retry_attempts
        self._retry_base_delay = retry_base_delay

    async def _get(self, url: str, params: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return await fetch_with_retry(
                lambda: self._client.get(url, params=params),  # type: ignore[union-attr]
                attempts=self._retry_attempts,
                base_delay=self._retry_base_delay,
            )
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": "ResearchOS/0.2 (+research-copilot)"}
        ) as client:
            return await fetch_with_retry(
                lambda: client.get(url, params=params),
                attempts=self._retry_attempts,
                base_delay=self._retry_base_delay,
            )

    async def search(
        self,
        query: str,
        *,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]:
        params: dict[str, str] = {
            "query": query,
            "offset": str(filters.offset if filters is not None else 0),
            "limit": str(limit),
            "fields": _FIELDS,
        }
        if filters is not None:
            start, end = filters.date_window()
            if start is not None or end is not None:
                params["publicationDateOrYear"] = (
                    f"{start.isoformat() if start else ''}:{end.isoformat() if end else ''}"
                )
        # Categories and sort are unsupported by S2 search; the federated
        # layer handles "latest" ordering.
        try:
            resp = await self._get(f"{self._base_url}/paper/search", params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("s2_fetch_failed", error=str(exc))
            raise ProviderError("Failed to query Semantic Scholar.") from exc
        return [_item_to_result(item) for item in data.get("data") or []]

    async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]:
        results: list[PaperResult] = []
        for paper_id in ids[:50]:
            try:
                resp = await self._get(
                    f"{self._base_url}/paper/{paper_id}", {"fields": _FIELDS}
                )
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                results.append(_item_to_result(resp.json()))
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("s2_fetch_by_id_failed", paper_id=paper_id, error=str(exc))
                raise ProviderError("Failed to fetch papers from Semantic Scholar.") from exc
        return results
