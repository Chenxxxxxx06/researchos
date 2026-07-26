"""Federated paper search: fan-out, per-provider timeouts, dedup and merge.

``merge_results`` is a pure function: union-find over DOI / arXiv id / title
identity plus a conservative fuzzy pass, then a source-priority field merge
(arxiv > s2 > openalex) that preserves full provenance in ``extra["sources"]``.
"""

from __future__ import annotations

import asyncio
import difflib
import unicodedata

import structlog

from researchos.common.config import get_settings

from .arxiv import _VERSION_RE
from .base import PaperResult, PaperSearchFilters, ProviderError

logger = structlog.get_logger(__name__)

RRF_K = 60
_FUZZY_THRESHOLD = 0.92
_SOURCE_PRIORITY = {"arxiv": 0, "s2": 1, "openalex": 2}


def normalize_doi(doi: str) -> str:
    value = doi.strip().lower()
    for prefix in ("doi:", "https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        value = value.removeprefix(prefix)
    return value


def normalize_arxiv_id(arxiv_id: str) -> str:
    return _VERSION_RE.sub("", arxiv_id.strip())


def normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in stripped).split())


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[max(ri, rj)] = min(ri, rj)


def _result_arxiv_id(result: PaperResult) -> str | None:
    if result.source == "arxiv":
        return normalize_arxiv_id(result.external_id)
    raw = result.extra.get("arxiv_id")
    return normalize_arxiv_id(raw) if isinstance(raw, str) and raw else None


def _first_author_last_name(result: PaperResult) -> str | None:
    if not result.authors:
        return None
    parts = result.authors[0].split()
    return parts[-1].lower() if parts else None


def _priority(result: PaperResult) -> int:
    return _SOURCE_PRIORITY.get(result.source, 99)


def _rrf_raw(ranks: list[int]) -> float:
    return sum(1.0 / (RRF_K + rank) for rank in ranks)


def merge_results(by_provider: dict[str, list[PaperResult]]) -> list[PaperResult]:
    """Deduplicate and merge per-provider result lists into one ranked list."""

    entries: list[tuple[int, PaperResult]] = []  # (provider rank, result)
    for results in by_provider.values():
        for rank, result in enumerate(results):
            entries.append((rank, result))
    if not entries:
        return []

    uf = _UnionFind(len(entries))

    def _union_by_key(key_of) -> None:
        seen: dict[str, int] = {}
        for idx, (_, result) in enumerate(entries):
            key = key_of(result)
            if not key:
                continue
            if key in seen:
                uf.union(seen[key], idx)
            else:
                seen[key] = idx

    _union_by_key(lambda r: normalize_doi(r.doi) if r.doi else None)
    _union_by_key(_result_arxiv_id)
    _union_by_key(lambda r: normalize_title(r.title) if r.title else None)

    # Fuzzy pass: only between results still in singleton components.
    sizes: dict[int, int] = {}
    for idx in range(len(entries)):
        root = uf.find(idx)
        sizes[root] = sizes.get(root, 0) + 1
    singles = [idx for idx in range(len(entries)) if sizes[uf.find(idx)] == 1]
    norm_titles = {idx: normalize_title(entries[idx][1].title) for idx in singles}
    for pos, i in enumerate(singles):
        for j in singles[pos + 1 :]:
            if uf.find(i) == uf.find(j):
                continue
            ti, tj = norm_titles[i], norm_titles[j]
            if not ti or not tj:
                continue
            if difflib.SequenceMatcher(None, ti, tj).ratio() < _FUZZY_THRESHOLD:
                continue
            ri, rj = entries[i][1], entries[j][1]
            author_match = (
                _first_author_last_name(ri) is not None
                and _first_author_last_name(ri) == _first_author_last_name(rj)
            )
            yi = ri.published_at.year if ri.published_at else None
            yj = rj.published_at.year if rj.published_at else None
            year_match = yi is not None and yj is not None and abs(yi - yj) <= 1
            if author_match or year_match:
                uf.union(i, j)

    groups: dict[int, list[tuple[int, PaperResult]]] = {}
    for idx, entry in enumerate(entries):
        groups.setdefault(uf.find(idx), []).append(entry)

    merged: list[tuple[float, PaperResult]] = []
    for group in groups.values():
        merged.append(_merge_group(group))
    merged.sort(key=lambda item: (-item[0], normalize_title(item[1].title)))
    return [result for _, result in merged]


def _merge_group(group: list[tuple[int, PaperResult]]) -> tuple[float, PaperResult]:
    ordered = sorted(group, key=lambda item: (_priority(item[1]), item[0]))
    best = ordered[0][1]
    members = [result for _, result in ordered]

    def _first_non_null(getter):
        for member in members:
            value = getter(member)
            if value is not None:
                return value
        return None

    abstract = max(
        (m.abstract for m in members if m.abstract), key=len, default=None
    )
    authors = max((m.authors for m in members), key=len, default=[])
    venue = next(
        (m.venue for m in members if m.venue and m.venue != "arXiv"),
        "arXiv" if any(m.venue == "arXiv" for m in members) else None,
    )
    citation_counts = [m.citation_count for m in members if m.citation_count is not None]
    categories = list(dict.fromkeys(c for m in members for c in m.categories))

    # Lowest priority first so higher-priority extras win on key collisions.
    extra: dict = {}
    for member in reversed(members):
        extra.update(member.extra)
    extra["sources"] = [
        {
            "provider": result.source,
            "external_id": result.external_id,
            "url": result.url,
            "rank": rank,
        }
        for rank, result in ordered
    ]
    arxiv_id = next((aid for m in members if (aid := _result_arxiv_id(m))), None)
    if arxiv_id:
        extra["arxiv_id"] = arxiv_id

    merged = PaperResult(
        source=best.source,
        external_id=best.external_id,
        title=best.title,
        abstract=abstract,
        authors=authors,
        venue=venue,
        published_at=best.published_at or _first_non_null(lambda m: m.published_at),
        url=best.url,
        pdf_url=best.pdf_url or _first_non_null(lambda m: m.pdf_url),
        doi=_first_non_null(lambda m: normalize_doi(m.doi) if m.doi else None),
        citation_count=max(citation_counts) if citation_counts else None,
        categories=categories,
        extra=extra,
    )
    return _rrf_raw([rank for rank, _ in ordered]), merged


class FederatedProvider:
    """Fans a search out to several providers and merges the results.

    One failed provider never fails the search; per-provider outcomes are
    recorded in ``last_status`` (``ok | timeout | error:<code>``).
    """

    name = "federated"

    def __init__(self, providers: list, *, timeout_seconds: float | None = None) -> None:
        self.providers = providers
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else get_settings().provider_timeout_seconds
        )
        self.last_status: dict[str, str] = {}

    async def search(
        self,
        query: str,
        *,
        limit: int,
        filters: PaperSearchFilters | None = None,
    ) -> list[PaperResult]:
        async def _one(provider) -> list[PaperResult]:
            return await asyncio.wait_for(
                provider.search(query, limit=limit, filters=filters), timeout=self._timeout
            )

        outcomes = await asyncio.gather(
            *(_one(p) for p in self.providers), return_exceptions=True
        )
        status: dict[str, str] = {}
        by_provider: dict[str, list[PaperResult]] = {}
        for provider, outcome in zip(self.providers, outcomes, strict=False):
            if isinstance(outcome, TimeoutError):
                status[provider.name] = "timeout"
            elif isinstance(outcome, ProviderError):
                status[provider.name] = f"error:{outcome.code}"
            elif isinstance(outcome, BaseException):
                logger.warning(
                    "federated_provider_failed", provider=provider.name, error=str(outcome)
                )
                status[provider.name] = "error:internal_error"
            else:
                status[provider.name] = "ok"
                by_provider[provider.name] = outcome
        self.last_status = status
        if not by_provider:
            raise ProviderError("All paper search providers failed.")
        return merge_results(by_provider)

    async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]:
        # Import verification resolves a concrete provider by source name;
        # the federated facade never fetches by id.
        raise ProviderError("The federated provider cannot fetch by ids.")
