"""Server-side session store backed by Redis (see PHASE1_DECISIONS P1-D2).

Sessions are opaque tokens; no user data lives in the cookie. The session id
maps to a small JSON record in Redis with a sliding TTL.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime

from researchos.common.config import get_settings
from researchos.common.redis import get_redis

SESSION_PREFIX = "session:"


def _key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


async def create_session(user_id: str) -> str:
    """Create a session for a user and return the opaque session id."""

    session_id = secrets.token_urlsafe(32)
    settings = get_settings()
    record = {"user_id": user_id, "created_at": _now_iso(), "last_seen": _now_iso()}
    await get_redis().set(_key(session_id), json.dumps(record), ex=settings.session_ttl_seconds)
    return session_id


async def read_session(session_id: str) -> dict | None:
    """Return the session record, refreshing its TTL (sliding expiry)."""

    if not session_id:
        return None
    redis = get_redis()
    raw = await redis.get(_key(session_id))
    if raw is None:
        return None
    settings = get_settings()
    # Sliding expiration.
    await redis.expire(_key(session_id), settings.session_ttl_seconds)
    return json.loads(raw)


async def revoke_session(session_id: str) -> None:
    if session_id:
        await get_redis().delete(_key(session_id))
