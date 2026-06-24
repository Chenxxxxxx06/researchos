"""Cross-tenant isolation and role-based permission tests.

These prove that user A cannot reach user B's organization or projects, and that
project role ladders are enforced in the service layer.
"""

from __future__ import annotations

from httpx import AsyncClient

from .helpers import csrf_headers, register


async def _org_id(client: AsyncClient) -> str:
    return (await client.get("/organizations")).json()[0]["id"]


async def _create_project(client: AsyncClient, org_id: str, name: str = "Proj") -> dict:
    resp = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": name},
        headers=csrf_headers(client),
    )
    resp.raise_for_status()
    return resp.json()


async def test_user_cannot_read_other_users_project(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="a@example.com")
    await register(b, email="b@example.com")

    a_org = await _org_id(a)
    project = await _create_project(a, a_org)

    # B cannot read A's project — existence is hidden (404).
    resp = await b.get(f"/projects/{project['id']}")
    assert resp.status_code == 404


async def test_user_cannot_list_projects_in_other_org(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="a2@example.com")
    await register(b, email="b2@example.com")

    a_org = await _org_id(a)
    await _create_project(a, a_org)

    # B is not a member of A's org -> 404 (cannot even enumerate).
    resp = await b.get(f"/projects?organization_id={a_org}")
    assert resp.status_code == 404


async def test_user_cannot_create_project_in_other_org(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="a3@example.com")
    await register(b, email="b3@example.com")

    a_org = await _org_id(a)
    resp = await b.post(
        "/projects",
        json={"organization_id": a_org, "name": "Intrusion"},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404


async def test_viewer_cannot_update_project(make_client) -> None:
    owner = make_client()
    viewer = make_client()
    await register(owner, email="owner-perm@example.com")
    await register(viewer, email="viewer-perm@example.com")

    org_id = await _org_id(owner)
    project = await _create_project(owner, org_id)

    # Add viewer to org and project as viewer.
    await owner.post(
        f"/organizations/{org_id}/members",
        json={"email": "viewer-perm@example.com", "role": "member"},
        headers=csrf_headers(owner),
    )
    await owner.post(
        f"/projects/{project['id']}/members",
        json={"email": "viewer-perm@example.com", "role": "viewer"},
        headers=csrf_headers(owner),
    )

    # Viewer can read but not update.
    assert (await viewer.get(f"/projects/{project['id']}")).status_code == 200
    resp = await viewer.patch(
        f"/projects/{project['id']}",
        json={"name": "Hacked"},
        headers=csrf_headers(viewer),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "permission_denied"


async def test_org_admin_has_implicit_project_access(make_client) -> None:
    owner = make_client()
    admin = make_client()
    await register(owner, email="o-admin@example.com")
    await register(admin, email="org-admin@example.com")

    org_id = await _org_id(owner)
    project = await _create_project(owner, org_id)

    # Promote the second user to org admin (no explicit project membership).
    await owner.post(
        f"/organizations/{org_id}/members",
        json={"email": "org-admin@example.com", "role": "admin"},
        headers=csrf_headers(owner),
    )

    # Org admin gets implicit project admin: can read and update.
    assert (await admin.get(f"/projects/{project['id']}")).status_code == 200
    resp = await admin.patch(
        f"/projects/{project['id']}",
        json={"name": "Admin Rename"},
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200


async def test_org_admin_can_archive_project(make_client) -> None:
    owner = make_client()
    admin = make_client()
    await register(owner, email="archive-owner@example.com")
    await register(admin, email="archive-admin@example.com")

    org_id = await _org_id(owner)
    project = await _create_project(owner, org_id)

    await owner.post(
        f"/organizations/{org_id}/members",
        json={"email": "archive-admin@example.com", "role": "admin"},
        headers=csrf_headers(owner),
    )

    resp = await admin.delete(
        f"/projects/{project['id']}",
        headers=csrf_headers(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
