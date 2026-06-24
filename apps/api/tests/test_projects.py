"""Project CRUD, soft-delete, and membership tests."""

from __future__ import annotations

from httpx import AsyncClient

from .helpers import csrf_headers, register


async def _org_id(client: AsyncClient) -> str:
    orgs = (await client.get("/organizations")).json()
    return orgs[0]["id"]


async def _create_project(client: AsyncClient, org_id: str, name: str = "Proj") -> dict:
    resp = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": name},
        headers=csrf_headers(client),
    )
    resp.raise_for_status()
    return resp.json()


async def test_create_project_makes_owner_member(client: AsyncClient) -> None:
    await register(client, email="pm@example.com", display_name="PM")
    org_id = await _org_id(client)
    project = await _create_project(client, org_id, "My Project")
    assert project["status"] == "active"

    members = (await client.get(f"/projects/{project['id']}/members")).json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == "pm@example.com"


async def test_list_projects_scoped_to_org(client: AsyncClient) -> None:
    await register(client, email="list@example.com")
    org_id = await _org_id(client)
    await _create_project(client, org_id, "P1")
    await _create_project(client, org_id, "P2")

    page = (await client.get(f"/projects?organization_id={org_id}")).json()
    assert page["total"] == 2
    assert len(page["items"]) == 2


async def test_update_project(client: AsyncClient) -> None:
    await register(client, email="upd@example.com")
    org_id = await _org_id(client)
    project = await _create_project(client, org_id)

    resp = await client.patch(
        f"/projects/{project['id']}",
        json={"name": "Renamed", "field": "NLP"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["field"] == "NLP"


async def test_archive_is_soft_delete(client: AsyncClient) -> None:
    await register(client, email="arch@example.com")
    org_id = await _org_id(client)
    project = await _create_project(client, org_id)

    resp = await client.delete(f"/projects/{project['id']}", headers=csrf_headers(client))
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Excluded from default listing, present when include_archived=true.
    default = (await client.get(f"/projects?organization_id={org_id}")).json()
    assert default["total"] == 0
    archived = (
        await client.get(f"/projects?organization_id={org_id}&include_archived=true")
    ).json()
    assert archived["total"] == 1

    # Still fetchable by id (record not physically deleted).
    detail = await client.get(f"/projects/{project['id']}")
    assert detail.status_code == 200


async def test_add_project_member_flow(make_client) -> None:
    owner = make_client()
    member = make_client()
    await register(owner, email="owner@example.com", display_name="Owner")
    await register(member, email="member@example.com", display_name="Member")

    org_id = await _org_id(owner)
    project = await _create_project(owner, org_id)

    # Owner adds the user to the organization first, then to the project.
    add_org = await owner.post(
        f"/organizations/{org_id}/members",
        json={"email": "member@example.com", "role": "member"},
        headers=csrf_headers(owner),
    )
    assert add_org.status_code == 201

    add_proj = await owner.post(
        f"/projects/{project['id']}/members",
        json={"email": "member@example.com", "role": "researcher"},
        headers=csrf_headers(owner),
    )
    assert add_proj.status_code == 201
    assert add_proj.json()["role"] == "researcher"

    # The member can now see the project.
    seen = await member.get(f"/projects/{project['id']}")
    assert seen.status_code == 200


async def test_add_member_requires_org_membership(make_client) -> None:
    owner = make_client()
    outsider = make_client()
    await register(owner, email="owner2@example.com")
    await register(outsider, email="outsider@example.com")

    org_id = await _org_id(owner)
    project = await _create_project(owner, org_id)

    # Outsider is not in the org -> validation error.
    resp = await owner.post(
        f"/projects/{project['id']}/members",
        json={"email": "outsider@example.com", "role": "researcher"},
        headers=csrf_headers(owner),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
