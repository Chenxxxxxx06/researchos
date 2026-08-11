"""Zotero Web API connection checks and incremental metadata sync."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import AppError, NotFoundError
from researchos.common.roles import ProjectRole
from researchos.common.secrets import decrypt_secret, encrypt_secret
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.research.enums import PaperIngestStatus
from researchos.research.models import Paper

from .models import ZoteroConnection
from .schemas import (
    SaveZoteroConnectionRequest,
    ZoteroConnectionTestResponse,
    ZoteroSyncResponse,
)

ZOTERO_API_BASE = "https://api.zotero.org"
_PAGE_SIZE = 100
_YEAR_RE = re.compile(r"\b(18|19|20|21)\d{2}\b")


class ZoteroService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.db = db
        self.projects = ProjectService(db)
        self._http_client = http_client

    async def get(
        self, actor: User, project_id: uuid.UUID
    ) -> ZoteroConnection | None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.db.scalar(
            select(ZoteroConnection).where(ZoteroConnection.project_id == project_id)
        )

    async def save(
        self,
        actor: User,
        project_id: uuid.UUID,
        payload: SaveZoteroConnectionRequest,
    ) -> ZoteroConnection:
        await self.projects.ensure_access(actor, project_id, ProjectRole.ADMIN)
        connection = await self.db.scalar(
            select(ZoteroConnection).where(ZoteroConnection.project_id == project_id)
        )
        if connection is None:
            if not payload.api_key:
                raise AppError(
                    "Zotero API key is required for the first connection.",
                    code="validation_error",
                    http_status=422,
                )
            connection = ZoteroConnection(project_id=project_id)
            self.db.add(connection)
        connection.library_type = payload.library_type
        connection.library_id = payload.library_id.strip()
        if payload.api_key:
            connection.api_key = encrypt_secret(payload.api_key)
        connection.enabled = payload.enabled
        connection.include_collections_json = payload.include_collections
        await self.db.commit()
        await self.db.refresh(connection)
        return connection

    async def require_connection(
        self, actor: User, project_id: uuid.UUID, minimum_role: ProjectRole
    ) -> ZoteroConnection:
        await self.projects.ensure_access(actor, project_id, minimum_role)
        connection = await self.db.scalar(
            select(ZoteroConnection).where(ZoteroConnection.project_id == project_id)
        )
        if connection is None:
            raise NotFoundError("Zotero connection not configured.")
        return connection

    async def test(
        self, actor: User, project_id: uuid.UUID
    ) -> ZoteroConnectionTestResponse:
        connection = await self.require_connection(actor, project_id, ProjectRole.ADMIN)
        started = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.get(
                    f"{ZOTERO_API_BASE}/keys/current",
                    headers=self._headers(connection),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001 - typed diagnostic result
            return ZoteroConnectionTestResponse(
                ok=False,
                message=self._http_error(exc),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        access = data.get("access") if isinstance(data, dict) else {}
        user_access = access.get("user") if isinstance(access, dict) else {}
        key_user_id = str(data.get("userID")) if data.get("userID") else None
        library_access = bool(
            isinstance(user_access, dict)
            and user_access.get("library")
            and key_user_id == connection.library_id
        )
        if connection.library_type == "group":
            groups = access.get("groups") if isinstance(access, dict) else {}
            library_access = bool(
                isinstance(groups, dict)
                and connection.library_id in groups
            )
        return ZoteroConnectionTestResponse(
            ok=library_access,
            message=(
                "Zotero key and library access verified."
                if library_access
                else "The key is valid but has no library read permission."
            ),
            username=str(data.get("username")) if data.get("username") else None,
            user_id=key_user_id,
            library_access=library_access,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def sync(self, actor: User, project_id: uuid.UUID) -> ZoteroSyncResponse:
        connection = await self.require_connection(
            actor, project_id, ProjectRole.RESEARCHER
        )
        if not connection.enabled:
            raise AppError(
                "Zotero connection is disabled.",
                code="zotero_disabled",
                http_status=409,
            )

        prefix = (
            f"groups/{connection.library_id}"
            if connection.library_type == "group"
            else f"users/{connection.library_id}"
        )
        created = updated = linked = skipped = 0
        next_version = connection.last_library_version
        start = 0
        params: dict[str, Any] = {
            "format": "json",
            "include": "data",
            "limit": _PAGE_SIZE,
        }
        if connection.last_library_version:
            params["since"] = connection.last_library_version

        try:
            async with self._client() as client:
                while True:
                    params["start"] = start
                    response = await client.get(
                        f"{ZOTERO_API_BASE}/{prefix}/items/top",
                        headers=self._headers(connection),
                        params=params,
                    )
                    response.raise_for_status()
                    try:
                        next_version = max(
                            next_version,
                            int(response.headers.get("Last-Modified-Version", "0")),
                        )
                    except ValueError:
                        pass
                    rows = response.json()
                    if not isinstance(rows, list):
                        raise AppError(
                            "Unexpected Zotero response shape.",
                            code="zotero_error",
                            http_status=502,
                        )
                    for raw in rows:
                        outcome = await self._upsert_item(actor, project_id, raw)
                        if outcome == "created":
                            created += 1
                        elif outcome == "updated":
                            updated += 1
                        elif outcome == "linked":
                            linked += 1
                        else:
                            skipped += 1
                    if len(rows) < _PAGE_SIZE:
                        break
                    start += _PAGE_SIZE
        except Exception as exc:
            message = self._http_error(exc)
            await self.db.rollback()
            failed_connection = await self.db.scalar(
                select(ZoteroConnection).where(
                    ZoteroConnection.project_id == project_id
                )
            )
            if failed_connection is not None:
                failed_connection.last_error = message
                await self.db.commit()
            raise AppError(
                message,
                code="zotero_sync_failed",
                http_status=502,
            ) from exc

        now = datetime.now(tz=UTC)
        connection.last_library_version = next_version
        connection.last_synced_at = now
        connection.last_error = None
        await self.db.commit()
        return ZoteroSyncResponse(
            created=created,
            updated=updated,
            linked=linked,
            skipped=skipped,
            library_version=next_version,
            last_synced_at=now,
        )

    async def _upsert_item(
        self,
        actor: User,
        project_id: uuid.UUID,
        raw: Any,
    ) -> str:
        if not isinstance(raw, dict):
            return "skipped"
        data = raw.get("data")
        if not isinstance(data, dict):
            return "skipped"
        key = str(raw.get("key") or data.get("key") or "").strip()
        title = str(data.get("title") or "").strip()
        if not key or not title:
            return "skipped"

        doi = self._normalize_doi(data.get("DOI"))
        zotero_row = await self.db.scalar(
            select(Paper).where(
                Paper.project_id == project_id,
                Paper.source == "zotero",
                Paper.external_id == key,
            )
        )
        cross_row = None
        if zotero_row is None and doi:
            cross_row = await self.db.scalar(
                select(Paper).where(
                    Paper.project_id == project_id,
                    or_(Paper.doi == doi, Paper.doi == doi.lower()),
                )
            )

        metadata = self._metadata(raw, data)
        if cross_row is not None:
            current = dict(cross_row.metadata_json or {})
            current["zotero"] = metadata
            cross_row.metadata_json = current
            return "linked"

        authors = self._authors(data.get("creators"))
        abstract = str(data.get("abstractNote") or "").strip() or None
        venue = (
            str(
                data.get("publicationTitle")
                or data.get("conferenceName")
                or data.get("proceedingsTitle")
                or ""
            ).strip()
            or None
        )
        url = (
            str(data.get("url") or "").strip()
            or f"https://www.zotero.org/{'groups' if data.get('libraryCatalog') else 'users'}/"
            f"{key}"
        )
        published_at = self._parse_date(data.get("date"))

        if zotero_row is None:
            self.db.add(
                Paper(
                    project_id=project_id,
                    source="zotero",
                    external_id=key,
                    title=title,
                    abstract=abstract,
                    authors_json=authors,
                    venue=venue,
                    published_at=published_at,
                    url=url,
                    pdf_url=None,
                    doi=doi,
                    ingest_status=PaperIngestStatus.ABSTRACT_ONLY,
                    metadata_json=metadata,
                    imported_by=actor.id,
                )
            )
            return "created"

        zotero_row.title = title
        zotero_row.abstract = abstract
        zotero_row.authors_json = authors
        zotero_row.venue = venue
        zotero_row.published_at = published_at
        zotero_row.url = url
        zotero_row.doi = doi
        zotero_row.metadata_json = metadata
        return "updated"

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._http_client is not None:
            # Tests can inject a MockTransport-backed client. It is caller-owned.
            yield self._http_client
            return
        async with httpx.AsyncClient(timeout=30) as client:
            yield client

    @staticmethod
    def _headers(connection: ZoteroConnection) -> dict[str, str]:
        return {
            "Zotero-API-Version": "3",
            "Zotero-API-Key": decrypt_secret(connection.api_key),
            "Accept": "application/json",
        }

    @staticmethod
    def _authors(raw: Any) -> list[str]:
        if not isinstance(raw, list):
            return []
        authors: list[str] = []
        for creator in raw:
            if not isinstance(creator, dict):
                continue
            name = str(creator.get("name") or "").strip()
            if not name:
                name = " ".join(
                    part
                    for part in (
                        str(creator.get("firstName") or "").strip(),
                        str(creator.get("lastName") or "").strip(),
                    )
                    if part
                )
            if name:
                authors.append(name)
        return authors

    @staticmethod
    def _normalize_doi(raw: Any) -> str | None:
        value = str(raw or "").strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if value.startswith(prefix):
                value = value[len(prefix) :]
        return value or None

    @staticmethod
    def _parse_date(raw: Any) -> datetime | None:
        value = str(raw or "").strip()
        match = _YEAR_RE.search(value)
        if not match:
            return None
        try:
            return datetime(int(match.group(0)), 1, 1, tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _metadata(raw: dict, data: dict) -> dict:
        return {
            "zotero_key": str(raw.get("key") or data.get("key") or ""),
            "zotero_version": int(raw.get("version") or data.get("version") or 0),
            "item_type": data.get("itemType"),
            "tags": [
                tag.get("tag")
                for tag in data.get("tags") or []
                if isinstance(tag, dict) and tag.get("tag")
            ],
            "collections": [
                str(collection) for collection in data.get("collections") or []
            ],
            "date_added": data.get("dateAdded"),
            "date_modified": data.get("dateModified"),
        }

    @staticmethod
    def _http_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 403:
                return "Zotero rejected the API key or library permission."
            if status == 404:
                return "Zotero library was not found. Check the library type and ID."
            if status == 429:
                return "Zotero rate limit reached. Please retry later."
            return f"Zotero API returned HTTP {status}."
        if isinstance(exc, httpx.TimeoutException):
            return "Zotero API connection timed out."
        return (str(exc).strip() or exc.__class__.__name__)[:500]
