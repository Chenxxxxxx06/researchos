"""Thin Redis pub/sub helpers for project-scoped event fan-out."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from researchos.common.redis import get_redis


def project_channel(project_id: str) -> str:
    return f"ws:project:{project_id}"


async def publish_event(project_id: str, envelope: dict) -> None:
    await get_redis().publish(project_channel(project_id), json.dumps(envelope))


async def subscribe_project(project_id: str) -> AsyncIterator[dict]:
    """Yield decoded event envelopes published to a project channel."""

    pubsub = get_redis().pubsub()
    await pubsub.subscribe(project_channel(project_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if data is None:
                continue
            try:
                yield json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
    finally:
        await pubsub.unsubscribe(project_channel(project_id))
        await pubsub.aclose()
