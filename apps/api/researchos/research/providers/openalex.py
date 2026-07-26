"""OpenAlex works provider.

No API key; a ``mailto`` contact (polite pool) is attached when configured.
Abstracts are reconstructed from OpenAlex's inverted index.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
import structlog

from researchos.common.config import get_settings

from .base import PaperResult, PaperSearchFilters, ProviderError
from .retry import fetch_with_retry

logger = structlog.get_logger(__name__)

_OPENALEX_ID_PREFIX = "https://openalex.org/"
_DOI_PREFIX = "https://doi.org/"
_ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/(?P<id>[a-z\-]+(?:\.[A-Za-z\-]+)?/\d{7}|\d{4}\.\d{4,5})",
    re.IGNORECASE,
)


def _abstract_from_inverted_index(index: dict | None) -> str | None:
    if not index:
        return None
    positions: dict[int, str] = {}
    for word, occurrences in index.items():
        for pos in occurrences:
            positions[int(pos)] = word
    if not positions:
        return None
    return " ".join(positions[pos] for pos in sorted(positions))


def _short_id(raw: str | None) -> str:
    value = raw or ""
    if value.startswith(_OPENALEX_ID_PREFIX):
        return value[len(_OPENALEX_ID_PREFIX) :]
    return value


def _extract_arxiv_id(item: dict) -> str | None:
    candidates: list[str] = []
    primary = item.get("primary_location") or {}
    if primary.get("landing_page_url"):
        candidates.append(primary["landing_page_url"])
    if primary.get("pdf_url"):
        candidates.append(primary["pdf_url"])
    for location in item.get("locations") or []:
        if location.get("pdf_url"):
            candidates.append(location["pdf_url"])
        if location.get("landing_page_url"):
            candidates.append(location["landing_page_url"])
    for url in candidates:
        match = _ARXIV_URL_RE.search(url)
        if match:
            return match.group("id")
    return None


def _item_to_result(item: dict) -> PaperResult:
    short_id = _short_id(item.get("id"))
    ids = item.get("ids") or {}
    doi = ids.get("doi") or item.get("doi")
    if isinstance(doi, str) and doi:
        doi = doi.removeprefix(_DOI_PREFIX).removeprefix("http://doi.org/").lower()
    else:
        doi = None

    primary = item.get("primary_location") or {}
    source = primary.get("source") or {}
    published_at: datetime | None = None
    if item.get("publication_date"):
        try:
            published_at = datetime.fromisoformat(item["publication_date"]).replace(tzinfo=UTC)
        except ValueError:
            published_at = None

    extra: dict = {}
    arxiv_id = _extract_arxiv_id(item)
    if arxiv_id:
        extra["arxiv_id"] = arxiv_id

    return PaperResult(
        source="openalex",
        external_id=short_id,
        title=item.get("title") or item.get("display_name") or "",
        abstract=_abstract_from_inverted_index(item.get("abstract_inverted_index")),
        authors=[
            (a.get("author") or {}).get("display_name", "")
            for a in item.get("authorships") or []
        ],
        venue=source.get("display_name"),
        published_at=published_at,
        url=primary.get("landing_page_url") or f"{_OPENALEX_ID_PREFIX}{short_id}",
        pdf_url=primary.get("pdf_url"),
        doi=doi,
        citation_count=item.get("cited_by_count"),
        extra=extra,
    )


class OpenAlexProvider:
    name = "openalex"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        *,
        mailto: str | None = None,
        retry_base_delay: float = 0.5,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = (base_url or settings.openalex_api_base).rstrip("/")
        self._mailto = settings.openalex_mailto if mailto is None else mailto
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
        offset = filters.offset if filters is not None else 0
        params: dict[str, str] = {
            "search": query,
            "per-page": str(limit),
            "page": str(offset // max(limit, 1) + 1),
        }
        if self._mailto:
            params["mailto"] = self._mailto
        if filters is not None:
            start, end = filters.date_window()
            filter_parts: list[str] = []
            if start is not None:
                filter_parts.append(f"from_publication_date:{start.isoformat()}")
            if end is not None:
                filter_parts.append(f"to_publication_date:{end.isoformat()}")
            if filter_parts:
                params["filter"] = ",".join(filter_parts)
            if filters.sort == "latest":
                params["sort"] = "publication_date:desc"
        # Categories ignored: no arXiv-taxonomy mapping in v1.
        try:
            resp = await self._get(f"{self._base_url}/works", params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("openalex_fetch_failed", error=str(exc))
            raise ProviderError("Failed to query OpenAlex.") from exc
        return [_item_to_result(item) for item in data.get("results") or []]

    async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]:
        results: list[PaperResult] = []
        params: dict[str, str] = {}
        if self._mailto:
            params["mailto"] = self._mailto
        for work_id in ids[:50]:
            try:
                resp = await self._get(f"{self._base_url}/works/{work_id}", params)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                results.append(_item_to_result(resp.json()))
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("openalex_fetch_by_id_failed", work_id=work_id, error=str(exc))
                raise ProviderError("Failed to fetch papers from OpenAlex.") from exc
        return results
