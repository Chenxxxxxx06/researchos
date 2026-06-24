"""Agent run API tests (creation, listing, events fallback, cancel).

Execution itself is covered by test_agent_runtime; here the worker is not
consuming, so runs remain queued, which is what these endpoint tests assert.
"""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_create_research_run_returns_handle(client) -> None:
    project_id = await _make_project(client, "ar@example.com")
    resp = await client.post(
        f"/projects/{project_id}/agents/runs",
        json={"agent_type": "research", "message": "find papers"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["stream"].startswith("/ws?project_id=")

    run_id = body["agent_run_id"]
    detail = await client.get(f"/projects/{project_id}/agents/runs/{run_id}")
    assert detail.status_code == 200
    listing = (await client.get(f"/projects/{project_id}/agents/runs")).json()
    assert listing["total"] == 1


async def test_events_rest_fallback(client) -> None:
    project_id = await _make_project(client, "ev@example.com")
    run_id = (
        await client.post(
            f"/projects/{project_id}/agents/runs",
            json={"agent_type": "research", "message": "x"},
            headers=csrf_headers(client),
        )
    ).json()["agent_run_id"]

    # No worker consumed the run, so there are no events yet, but the endpoint works.
    resp = await client.get(f"/projects/{project_id}/agents/runs/{run_id}/events?after_seq=-1")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_cancel_queued_run(client) -> None:
    project_id = await _make_project(client, "cancel@example.com")
    run_id = (
        await client.post(
            f"/projects/{project_id}/agents/runs",
            json={"agent_type": "research", "message": "x"},
            headers=csrf_headers(client),
        )
    ).json()["agent_run_id"]

    resp = await client.post(
        f"/projects/{project_id}/agents/runs/{run_id}/cancel", headers=csrf_headers(client)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_critic_run_requires_idea(client) -> None:
    project_id = await _make_project(client, "needidea@example.com")
    resp = await client.post(
        f"/projects/{project_id}/agents/runs",
        json={"agent_type": "critic", "message": "x"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
