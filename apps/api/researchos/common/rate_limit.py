"""Simple Redis fixed-window rate limiter."""

from __future__ import annotations

from researchos.common.errors import AppError
from researchos.common.redis import get_redis


class RateLimitedError(AppError):
    code = "rate_limited"
    http_status = 429
    message = "Rate limit exceeded. Please slow down."


async def enforce_rate_limit(key: str, *, limit: int, window_seconds: int = 60) -> None:
    """Increment a per-key counter in the current window and raise if over limit.

    A non-positive ``limit`` disables the check (useful in tests).
    """

    if limit <= 0:
        return
    redis = get_redis()
    bucket = f"ratelimit:{key}"
    count = await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, window_seconds)
    if count > limit:
        raise RateLimitedError()
