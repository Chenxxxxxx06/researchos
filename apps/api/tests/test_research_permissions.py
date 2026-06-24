"""Cross-tenant isolation for Research Copilot endpoints."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_outsider_cannot_search_papers(make_client) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "rp-a@example.com")
    await register(b, email="rp-b@example.com")

    resp = await b.post(
        f"/projects/{project_id}/papers/search",
        json={"query": "x", "limit": 5},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404


async def test_outsider_cannot_create_agent_run(make_client) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "rp2-a@example.com")
    await register(b, email="rp2-b@example.com")

    resp = await b.post(
        f"/projects/{project_id}/agents/runs",
        json={"agent_type": "research", "message": "x"},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404


async def test_outsider_cannot_list_runs(make_client) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "rp3-a@example.com")
    await register(b, email="rp3-b@example.com")

    resp = await b.get(f"/projects/{project_id}/agents/runs")
    assert resp.status_code == 404
