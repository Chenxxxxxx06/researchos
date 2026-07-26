"""Best-effort WS event publishing for experiments/anchors/figures.

All producers here fire after commit and never fail the request. Figure
events require the ``"figure"`` resource type, which lands with M1's
``websocket/envelopes.py`` change — until then they are withheld
(the feature is poll-complete via ``GET /figures/{fid}``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, get_args

import structlog

from researchos.common.pubsub import publish_event
from researchos.websocket.envelopes import EventEnvelope, ResourceType

logger = structlog.get_logger(__name__)

_FIGURE_RESOURCE_SUPPORTED = "figure" in get_args(ResourceType)


def build_envelope(
    *,
    event_type: str,
    project_id: uuid.UUID | str,
    resource_type: str,
    resource_id: uuid.UUID | str,
    payload: dict[str, Any],
) -> dict:
    return EventEnvelope(
        event_type=event_type,
        project_id=str(project_id),
        resource_type=resource_type,
        resource_id=str(resource_id),
        timestamp=datetime.now(tz=UTC).isoformat(),
        payload=payload,
    ).model_dump()


async def publish_best_effort(project_id: uuid.UUID | str, envelope: dict) -> None:
    try:
        await publish_event(str(project_id), envelope)
    except Exception as exc:  # pragma: no cover - depends on broker availability
        logger.warning("ws_publish_failed", event_type=envelope.get("event_type"), error=str(exc))


async def publish_run_event(
    *,
    event_type: str,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    envelope = build_envelope(
        event_type=event_type,
        project_id=project_id,
        resource_type="experiment_run",
        resource_id=run_id,
        payload=payload,
    )
    await publish_best_effort(project_id, envelope)


async def publish_anchor_values_updated(
    *,
    project_id: uuid.UUID,
    updated_count: int,
    stale_count: int,
    anchor_ids: list[str],
) -> None:
    envelope = build_envelope(
        event_type="anchor.values.updated",
        project_id=project_id,
        resource_type="project",
        resource_id=project_id,
        payload={
            "updated_count": updated_count,
            "stale_count": stale_count,
            "anchor_ids": anchor_ids,
        },
    )
    await publish_best_effort(project_id, envelope)


async def publish_figure_event(
    *,
    event_type: str,
    project_id: uuid.UUID,
    figure_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    # Withheld until the "figure" resource type ships (M1 envelopes change).
    if not _FIGURE_RESOURCE_SUPPORTED:
        return
    envelope = build_envelope(
        event_type=event_type,
        project_id=project_id,
        resource_type="figure",
        resource_id=figure_id,
        payload=payload,
    )
    await publish_best_effort(project_id, envelope)
