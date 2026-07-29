"""Project-scoped Zotero connection and synchronization endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .models import ZoteroConnection
from .schemas import (
    SaveZoteroConnectionRequest,
    ZoteroConnectionResponse,
    ZoteroConnectionTestResponse,
    ZoteroSyncResponse,
)
from .service import ZoteroService

router = APIRouter(prefix="/projects/{project_id}/integrations/zotero", tags=["zotero"])


def _response(connection: ZoteroConnection) -> ZoteroConnectionResponse:
    key = connection.api_key
    masked = f"****{key[-4:]}" if len(key) > 4 else "****"
    return ZoteroConnectionResponse(
        id=str(connection.id),
        library_type=connection.library_type,
        library_id=connection.library_id,
        api_key_masked=masked,
        enabled=connection.enabled,
        include_collections=[str(v) for v in connection.include_collections_json],
        last_library_version=connection.last_library_version,
        last_synced_at=connection.last_synced_at,
        last_error=connection.last_error,
    )


@router.get("", response_model=ZoteroConnectionResponse | None)
async def get_connection(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ZoteroConnectionResponse | None:
    connection = await ZoteroService(db).get(user, project_id)
    return _response(connection) if connection is not None else None


@router.put(
    "",
    response_model=ZoteroConnectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def save_connection(
    project_id: uuid.UUID,
    payload: SaveZoteroConnectionRequest,
    user: CurrentUser,
    db: DbSession,
) -> ZoteroConnectionResponse:
    connection = await ZoteroService(db).save(user, project_id, payload)
    return _response(connection)


@router.post(
    "/test",
    response_model=ZoteroConnectionTestResponse,
    dependencies=[Depends(require_csrf)],
)
async def test_connection(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ZoteroConnectionTestResponse:
    return await ZoteroService(db).test(user, project_id)


@router.post(
    "/sync",
    response_model=ZoteroSyncResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
async def sync_library(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ZoteroSyncResponse:
    return await ZoteroService(db).sync(user, project_id)
