"""arXiv paper search provider.

Queries the public arXiv Atom API (no API key required) and normalizes the
results. The HTTP client is injectable so tests can serve recorded fixtures
without hitting the network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .base import PaperResult, PaperSearchFilters

logger = structlog.get_logger(__name__)


class ProviderError(AppError):
    code = "provider_error"
    http_status = 502
    message = "The paper search provider is unavailable."


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # arXiv uses ISO-8601 with a trailing Z.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _external_id(entry_id: str) -> str:
    # entry_id like "http://arxiv.org/abs/2401.01234v2" -> "2401.01234"
    tail = entry_id.rsplit("/abs/", 1)[-1]
    return tail.split("v")[0] if "v" in tail else tail


def _pdf_url(entry) -> str | None:
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf" or link.get("title") == "pdf":
            return link.get("href")
    return None


class ArxivProvider:
    name = "arxiv"

    def __init__(
        self, client: httpx.AsyncClient | None = None, base_url: str | None = None
    ) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = base_url or settings.arxiv_api_base
        self._timeout = settings.arxiv_timeout_seconds

    async def _fetch(self, params: dict[str, str]) -> str:
        if self._client is not None:
            resp = await self._client.get(self._base_url, params=params)
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": "ResearchOS/0.2 (+research-copilot)"}
        ) as client:
            resp = await client.get(self._base_url, params=params)
            resp.raise_for_status()
            return resp.text

    async def search(
        self,
        query: str,
        *,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]:
        params = {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(limit),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            raw = await self._fetch(params)
        except httpx.HTTPError as exc:
            logger.warning("arxiv_fetch_failed", error=str(exc))
            raise ProviderError("Failed to query arXiv.") from exc

        feed = feedparser.parse(raw)
        results: list[PaperResult] = []
        for entry in feed.entries:
            entry_id = entry.get("id", "")
            results.append(
                PaperResult(
                    source="arxiv",
                    external_id=_external_id(entry_id),
                    title=" ".join(entry.get("title", "").split()),
                    abstract=entry.get("summary"),
                    authors=[a.get("name", "") for a in entry.get("authors", [])],
                    venue="arXiv",
                    published_at=_parse_published(entry.get("published")),
                    url=entry.get("link", entry_id),
                    pdf_url=_pdf_url(entry),
                    extra={"arxiv_id": entry_id},
                )
            )
        return results
