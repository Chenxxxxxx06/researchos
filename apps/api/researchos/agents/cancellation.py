"""Cooperative agent-run cancellation via a Redis flag.

The API sets the flag; the runtime checks it cooperatively at safe points.
"""

from __future__ import annotations

import uuid

from researchos.common.redis import get_redis


def _key(run_id: uuid.UUID | str) -> str:
    return f"agent_cancel:{run_id}"


async def request_cancel(run_id: uuid.UUID | str) -> None:
    await get_redis().set(_key(run_id), "1", ex=3600)


async def is_cancel_requested(run_id: uuid.UUID | str) -> bool:
    return await get_redis().get(_key(run_id)) is not None
