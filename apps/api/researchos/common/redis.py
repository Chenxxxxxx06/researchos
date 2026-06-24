"""Async Redis client and a connectivity probe.

Redis is the Celery broker/result backend and (in later phases) the WebSocket
pub/sub fan-out and rate-limit store.
"""

from __future__ import annotations

from redis.asyncio import Redis

from .config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Return the process-wide async Redis client."""

    global _client
    if _client is None:
        settings = get_settings()
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def check_redis() -> None:
    """Raise if Redis is unreachable (used by the readiness probe)."""

    await get_redis().ping()


async def close_redis() -> None:
    """Close the Redis client on shutdown."""

    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
