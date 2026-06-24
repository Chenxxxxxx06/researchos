"""Organization endpoint and isolation tests."""

from __future__ import annotations

from httpx import AsyncClient

from .helpers import csrf_headers, register


async def test_list_organizations_after_register(client: AsyncClient) -> None:
    await register(client, email="og@example.com", display_name="OG")
    resp = await client.get("/organizations")
    assert resp.status_code == 200
    orgs = resp.json()
    assert len(orgs) == 1
    assert orgs[0]["role"] == "owner"


async def test_create_organization(client: AsyncClient) -> None:
    await register(client, email="multi@example.com")
    resp = await client.post(
        "/organizations", json={"name": "Second Lab"}, headers=csrf_headers(client)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Second Lab"

    listed = await client.get("/organizations")
    assert len(listed.json()) == 2


async def test_non_member_cannot_read_other_org(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="ownerA@example.com")
    await register(b, email="ownerB@example.com")

    a_orgs = (await a.get("/organizations")).json()
    a_org_id = a_orgs[0]["id"]

    # B is not a member of A's org -> hidden (404).
    resp = await b.get(f"/organizations/{a_org_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_org_members_listing(client: AsyncClient) -> None:
    await register(client, email="solo@example.com", display_name="Solo")
    orgs = (await client.get("/organizations")).json()
    resp = await client.get(f"/organizations/{orgs[0]['id']}/members")
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["email"] == "solo@example.com"
    assert members[0]["role"] == "owner"
