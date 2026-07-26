"""HTTP retry with exponential backoff for paper providers.

Deterministic jitter (no ``random``) keeps tests stable; the ``sleep``
callable is injectable so tests run instantly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def _backoff_delay(attempt: int, base_delay: float) -> float:
    # +/-25% deterministic jitter derived from the attempt index.
    jitter = ((hash(attempt) % 51) - 25) / 100.0
    return base_delay * (2**attempt) * (1.0 + jitter)


async def fetch_with_retry(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    retry_statuses: frozenset[int] = RETRY_STATUSES,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    """Call ``fn`` up to ``attempts`` times, retrying transport errors and
    retryable statuses.

    Returns the last response (callers ``raise_for_status`` as needed) or
    re-raises the final transport error.
    """

    attempts = max(1, attempts)
    response: httpx.Response | None = None
    for attempt in range(attempts):
        try:
            response = await fn()
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
        else:
            if response.status_code not in retry_statuses:
                return response
            if attempt == attempts - 1:
                return response
        await sleep(_backoff_delay(attempt, base_delay))
    assert response is not None  # unreachable: loop always returns or raises
    return response
