"""WebSocket envelope contract tests.

Asserts the backend agent event vocabulary and envelope shape stay aligned with
packages/shared-schemas (which the frontend depends on).
"""

from __future__ import annotations

import uuid

from researchos.websocket.envelopes import AGENT_EVENT_TYPES, build_agent_event

# This must match AGENT_EVENTS in packages/shared-schemas/src/events.ts.
_EXPECTED = {
    "agent.run.started",
    "agent.run.token",
    "agent.run.tool_call.started",
    "agent.run.tool_call.completed",
    "agent.run.completed",
    "agent.run.failed",
    "agent.run.cancelled",
}


def test_agent_event_types_match_shared_schema() -> None:
    assert set(AGENT_EVENT_TYPES) == _EXPECTED


def test_build_agent_event_envelope_shape() -> None:
    pid = uuid.uuid4()
    rid = uuid.uuid4()
    env = build_agent_event(
        event_type="agent.run.token",
        project_id=pid,
        agent_run_id=rid,
        payload={"delta": "hello"},
    )
    assert set(env.keys()) == {
        "event_id",
        "event_type",
        "project_id",
        "resource_type",
        "resource_id",
        "timestamp",
        "payload",
    }
    assert env["resource_type"] == "agent_run"
    assert env["project_id"] == str(pid)
    assert env["resource_id"] == str(rid)
    assert env["payload"] == {"delta": "hello"}
