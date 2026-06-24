"""Idea CRUD and permission tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_create_and_list_ideas(client) -> None:
    project_id = await _make_project(client, "idea@example.com")
    resp = await client.post(
        f"/projects/{project_id}/ideas",
        json={"title": "A novel method", "description": "desc"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"

    listing = (await client.get(f"/projects/{project_id}/ideas")).json()
    assert listing["total"] == 1


async def test_update_idea(client) -> None:
    project_id = await _make_project(client, "idea2@example.com")
    idea = (
        await client.post(
            f"/projects/{project_id}/ideas",
            json={"title": "T"},
            headers=csrf_headers(client),
        )
    ).json()
    resp = await client.patch(
        f"/projects/{project_id}/ideas/{idea['id']}",
        json={"status": "active", "hypothesis": "H"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert resp.json()["hypothesis"] == "H"


async def test_idea_tenant_isolation(make_client) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "idea-a@example.com")
    await register(b, email="idea-b@example.com")

    resp = await b.post(
        f"/projects/{project_id}/ideas",
        json={"title": "Intruder"},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404
