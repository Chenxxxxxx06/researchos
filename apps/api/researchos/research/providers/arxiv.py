"""arXiv paper search provider.

Queries the public arXiv Atom API (no API key required) and normalizes the
results. The HTTP client is injectable so tests can serve recorded fixtures
without hitting the network. User text is compiled into the arXiv query
language through a sanitizer so operators cannot be injected.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import feedparser
import httpx
import structlog

from researchos.common.config import get_settings

from .base import PaperResult, PaperSearchFilters
from .base import ProviderError as ProviderError  # re-export (historical import path)
from .retry import fetch_with_retry

logger = structlog.get_logger(__name__)

_VERSION_RE = re.compile(r"v(\d+)$")
# Characters that carry meaning in the arXiv query language.
_UNSAFE_RE = re.compile(r'["(){}\[\]:]')
_OPERATOR_TOKENS = {"AND", "OR", "ANDNOT", "NOT"}


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # arXiv uses ISO-8601 with a trailing Z.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _split_external_id(entry_id: str) -> tuple[str, str | None]:
    """Split an arXiv abs URL/id into (versionless id, version or None).

    Preserves old-style ids: ``solv-int/9701001`` -> (``solv-int/9701001``, None);
    ``2401.01234v2`` -> (``2401.01234``, ``v2``).
    """

    tail = entry_id.rsplit("/abs/", 1)[-1]
    match = _VERSION_RE.search(tail)
    return _VERSION_RE.sub("", tail), (match.group(0) if match else None)


def _sanitize_term(text: str) -> str:
    """Strip query-language grouping/operator characters, collapse whitespace."""

    return " ".join(_UNSAFE_RE.sub(" ", text).split())


def _fmt_date(value: date, *, end: bool) -> str:
    return value.strftime("%Y%m%d") + ("2359" if end else "0000")


def compile_arxiv_query(query: str, filters: PaperSearchFilters | None) -> str:
    """Compile free text + filters into a safe arXiv ``search_query`` string."""

    groups: list[str] = []

    tokens = [
        tok
        for tok in _sanitize_term(query).split()
        if tok.upper() not in _OPERATOR_TOKENS
    ]
    if tokens:
        groups.append("(" + " AND ".join(f"all:{tok}" for tok in tokens) + ")")

    if filters is not None:
        for prefix, value in (
            ("ti", filters.title),
            ("abs", filters.abstract),
            ("au", filters.author),
        ):
            if not value:
                continue
            term = _sanitize_term(value)
            if not term:
                continue
            groups.append(f'{prefix}:"{term}"' if " " in term else f"{prefix}:{term}")

        if filters.categories:
            groups.append("(" + " OR ".join(f"cat:{c}" for c in filters.categories) + ")")

        start, end = filters.date_window()
        if start is not None or end is not None:
            start_s = _fmt_date(start, end=False) if start else "190001010000"
            end_s = _fmt_date(end, end=True) if end else datetime.now(tz=UTC).strftime("%Y%m%d%H%M")
            groups.append(f"submittedDate:[{start_s} TO {end_s}]")

    if not groups:
        raise ProviderError("Empty query.")
    return " AND ".join(groups)


def _pdf_url(entry) -> str | None:
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf" or link.get("title") == "pdf":
            return link.get("href")
    return None


def _entry_to_result(entry) -> PaperResult:
    entry_id = entry.get("id", "")
    external_id, version = _split_external_id(entry_id)

    tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
    raw_primary = entry.get("arxiv_primary_category")
    primary = raw_primary.get("term") if isinstance(raw_primary, dict) else None
    if primary is None and tags:
        primary = tags[0]

    doi = entry.get("arxiv_doi")
    extra: dict = {"arxiv_id": external_id}
    if version:
        extra["arxiv_version"] = version
    if primary:
        extra["arxiv_primary_category"] = primary
    journal_ref = entry.get("arxiv_journal_ref")
    if journal_ref:
        extra["arxiv_journal_ref"] = journal_ref

    abstract = " ".join(entry.get("summary", "").split()) or None
    return PaperResult(
        source="arxiv",
        external_id=external_id,
        title=" ".join(entry.get("title", "").split()),
        abstract=abstract,
        authors=[a.get("name", "") for a in entry.get("authors", [])],
        venue="arXiv",
        published_at=_parse_published(entry.get("published")),
        url=entry.get("link", entry_id),
        pdf_url=_pdf_url(entry),
        doi=doi.lower() if isinstance(doi, str) and doi else None,
        citation_count=None,
        categories=tags,
        extra=extra,
    )


class ArxivProvider:
    name = "arxiv"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        *,
        retry_base_delay: float = 0.5,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = base_url or settings.arxiv_api_base
        self._timeout = settings.arxiv_timeout_seconds
        self._retry_attempts = settings.provider_retry_attempts
        self._retry_base_delay = retry_base_delay

    async def _fetch(self, params: dict[str, str]) -> str:
        if self._client is not None:
            resp = await fetch_with_retry(
                lambda: self._client.get(self._base_url, params=params),  # type: ignore[union-attr]
                attempts=self._retry_attempts,
                base_delay=self._retry_base_delay,
            )
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": "ResearchOS/0.2 (+research-copilot)"},
            follow_redirects=True,
        ) as client:
            resp = await fetch_with_retry(
                lambda: client.get(self._base_url, params=params),
                attempts=self._retry_attempts,
                base_delay=self._retry_base_delay,
            )
            resp.raise_for_status()
            return resp.text

    def _parse_feed(self, raw: str) -> list[PaperResult]:
        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            raise ProviderError("arXiv returned an unparseable feed.")
        return [_entry_to_result(entry) for entry in feed.entries]

    async def search(
        self,
        query: str,
        *,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]:
        sort = filters.sort if filters is not None else "relevance"
        offset = filters.offset if filters is not None else 0
        params = {
            "search_query": compile_arxiv_query(query, filters),
            "start": str(offset),
            "max_results": str(limit),
            "sortBy": "submittedDate" if sort == "latest" else "relevance",
            "sortOrder": "descending",
        }
        try:
            raw = await self._fetch(params)
        except httpx.HTTPError as exc:
            logger.warning("arxiv_fetch_failed", error=str(exc))
            raise ProviderError("Failed to query arXiv.") from exc
        return self._parse_feed(raw)

    async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]:
        """Fetch authoritative metadata for up to 50 ids in one batched request."""

        if not ids:
            return []
        params = {"id_list": ",".join(ids[:50]), "max_results": str(min(len(ids), 50))}
        try:
            raw = await self._fetch(params)
        except httpx.HTTPError as exc:
            logger.warning("arxiv_fetch_by_ids_failed", error=str(exc))
            raise ProviderError("Failed to fetch papers from arXiv.") from exc
        return self._parse_feed(raw)
