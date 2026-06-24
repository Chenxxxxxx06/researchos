"""WebSocket gateway endpoint.

Authenticates via the session cookie, verifies project membership in the service
layer, then relays project-scoped event envelopes from Redis pub/sub. Never
sends events across project boundaries.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from researchos.common.config import get_settings
from researchos.common.db import get_sessionmaker
from researchos.common.errors import AppError
from researchos.common.pubsub import subscribe_project
from researchos.common.roles import ProjectRole
from researchos.common.session import read_session
from researchos.identity.models import User
from researchos.projects.service import ProjectService

logger = structlog.get_logger(__name__)

router = APIRouter()

# Close codes (application-defined, in the 4xxx range).
_CLOSE_UNAUTHORIZED = 4401
_CLOSE_FORBIDDEN = 4403
_CLOSE_BAD_REQUEST = 4400


async def _authorize(websocket: WebSocket, project_id: uuid.UUID) -> bool:
    settings = get_settings()
    session_id = websocket.cookies.get(settings.session_cookie_name)
    record = await read_session(session_id) if session_id else None
    if record is None:
        await websocket.close(code=_CLOSE_UNAUTHORIZED)
        return False

    async with get_sessionmaker()() as db:
        try:
            user = await db.get(User, uuid.UUID(str(record["user_id"])))
        except (KeyError, ValueError):
            user = None
        if user is None or not user.is_active:
            await websocket.close(code=_CLOSE_UNAUTHORIZED)
            return False
        try:
            await ProjectService(db).ensure_access(user, project_id, ProjectRole.VIEWER)
        except AppError:
            await websocket.close(code=_CLOSE_FORBIDDEN)
            return False
    return True


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, project_id: str = Query(...)) -> None:
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        await websocket.close(code=_CLOSE_BAD_REQUEST)
        return

    if not await _authorize(websocket, pid):
        return

    await websocket.accept()
    logger.info("ws_connected", project_id=project_id)
    try:
        async for envelope in subscribe_project(project_id):
            await websocket.send_json(envelope)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - log and close on relay failure
        logger.warning("ws_relay_error", error=str(exc))
    finally:
        logger.info("ws_disconnected", project_id=project_id)
