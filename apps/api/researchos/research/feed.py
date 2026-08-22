"""Freshness feed: newest arXiv submissions in the project's followed areas.

Pull-based with a short-TTL Redis cache; no background daemon. Categories are
explicit prefs when present, else derived from the library's primary
categories (top categories until >=80% coverage, capped at 5).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import uuid

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.errors import ValidationError
from researchos.common.redis import get_redis
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .providers.arxiv import ArxivProvider
from .providers.base import PaperResult, PaperSearchFilters, ProviderError
from .ranking import rank_results
from .repository import FeedPrefRepository, PaperRepository
from .schemas import FeedCategoriesResponse, FeedItem, FeedResponse

logger = structlog.get_logger(__name__)

_DERIVED_COVERAGE = 0.80
_DERIVED_CAP = 5


def encode_cursor(offset: int) -> str:
    raw = json.dumps({"o": offset}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        offset = int(data["o"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ValidationError("Invalid feed cursor.") from exc
    if offset < 0:
        raise ValidationError("Invalid feed cursor.")
    return offset


class FeedService:
    def __init__(self, db: AsyncSession, *, http_client: httpx.AsyncClient | None = None) -> None:
        self.db = db
        self.papers = PaperRepository(db)
        self.prefs = FeedPrefRepository(db)
        self.projects = ProjectService(db)
        self._http_client = http_client

    async def _resolve_categories(self, project_id: uuid.UUID) -> tuple[list[str], bool]:
        """(categories, derived): explicit prefs win, else 80%-coverage derivation."""

        pref = await self.prefs.get(project_id)
        if pref is not None and pref.categories:
            return [str(c) for c in pref.categories], False
        counts = await self.papers.count_by_primary_category(project_id)
        total = sum(count for _, count in counts)
        if total == 0:
            return [], True
        derived: list[str] = []
        covered = 0
        for category, count in counts:
            derived.append(category)
            covered += count
            if covered / total >= _DERIVED_COVERAGE or len(derived) >= _DERIVED_CAP:
                break
        return derived, True

    async def get_categories(self, actor: User, project_id: uuid.UUID) -> FeedCategoriesResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        categories, derived = await self._resolve_categories(project_id)
        return FeedCategoriesResponse(categories=categories, derived=derived)

    async def set_categories(
        self, actor: User, project_id: uuid.UUID, categories: list[str]
    ) -> FeedCategoriesResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        await self.prefs.upsert(project_id, categories)
        await self.db.commit()
        resolved, derived = await self._resolve_categories(project_id)
        return FeedCategoriesResponse(categories=resolved, derived=derived)

    async def get_feed(
        self, actor: User, project_id: uuid.UUID, *, cursor: str | None, limit: int
    ) -> FeedResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        offset = decode_cursor(cursor) if cursor else 0
        categories, _ = await self._resolve_categories(project_id)
        if not categories:
            return FeedResponse(items=[], next_cursor=None, categories_used=[], cached=False)

        cats_digest = hashlib.sha1(",".join(categories).encode()).hexdigest()
        cache_key = f"feed:{project_id}:{cats_digest}:{offset}:{limit}"
        redis = get_redis()

        results: list[PaperResult] | None = None
        cached = False
        try:
            raw = await redis.get(cache_key)
        except Exception as exc:  # noqa: BLE001 - cache is best-effort
            logger.warning("feed_cache_read_failed", error=str(exc))
            raw = None
        if raw:
            try:
                results = [PaperResult.model_validate(item) for item in json.loads(raw)]
                cached = True
            except (json.JSONDecodeError, ValueError):
                results = None

        if results is None:
            provider = ArxivProvider(client=self._http_client)
            filters = PaperSearchFilters(categories=categories, sort="latest", offset=offset)
            try:
                results = await provider.search("", limit=limit, filters=filters)
            except ProviderError:
                # Offline degradation: nothing cached for this page -> surface
                # the provider error envelope (502).
                raise
            try:
                await redis.setex(
                    cache_key,
                    get_settings().feed_cache_ttl_seconds,
                    json.dumps([r.model_dump(mode="json") for r in results]),
                )
            except Exception as exc:  # noqa: BLE001 - cache is best-effort
                logger.warning("feed_cache_write_failed", error=str(exc))

        # Personalize at response time so a freshly synced Zotero library takes
        # effect immediately even when the provider response came from cache.
        library_docs, library_weights = await self.papers.list_library_interest_profile(
            project_id, limit=500
        )
        results = rank_results(
            list(results),
            library_docs=library_docs,
            library_weights=library_weights,
        )
        for result in results:
            result.extra["recommendation_algorithm"] = "zotero-library-recency-weighted-rrf-v2"

        # In-library markers are computed at response time (never cached).
        library_keys = await self.papers.list_ids_for_project(project_id)
        items = [
            FeedItem(**result.model_dump(), in_library=result.citation_key in library_keys)
            for result in results
        ]
        next_cursor = encode_cursor(offset + limit) if len(items) >= limit else None
        return FeedResponse(
            items=items, next_cursor=next_cursor, categories_used=categories, cached=cached
        )
