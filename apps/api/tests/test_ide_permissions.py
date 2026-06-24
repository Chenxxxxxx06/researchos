"""IDE workspace permission and tenant-isolation tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _org_project(owner) -> tuple[str, str]:
    org_id = (await owner.get("/organizations")).json()[0]["id"]
    project = (
        await owner.post(
            "/projects",
            json={"organization_id": org_id, "name": "P"},
            headers=csrf_headers(owner),
        )
    ).json()
    return org_id, project["id"]


async def _add_member(owner, org_id, project_id, email, role) -> None:
    await owner.post(
        f"/organizations/{org_id}/members",
        json={"email": email, "role": "member"},
        headers=csrf_headers(owner),
    )
    await owner.post(
        f"/projects/{project_id}/members",
        json={"email": email, "role": role},
        headers=csrf_headers(owner),
    )


async def test_non_member_cannot_access_workspace(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="ide-a@example.com")
    await register(b, email="ide-b@example.com")
    _org, project_id = await _org_project(a)

    resp = await b.get(f"/projects/{project_id}/workspace/tree")
    assert resp.status_code == 404


async def test_viewer_can_read_but_not_apply(make_client) -> None:
    owner = make_client()
    viewer = make_client()
    await register(owner, email="ide-owner@example.com")
    await register(viewer, email="ide-viewer@example.com")
    org_id, project_id = await _org_project(owner)
    await _add_member(owner, org_id, project_id, "ide-viewer@example.com", "viewer")

    # Viewer can read the tree.
    assert (await viewer.get(f"/projects/{project_id}/workspace/tree")).status_code == 200

    # Viewer cannot create a patch.
    create = await viewer.post(
        f"/projects/{project_id}/workspace/patches",
        json={
            "summary": "x",
            "files": [{"path": "f.txt", "change_type": "create", "new_content": "x"}],
        },
        headers=csrf_headers(viewer),
    )
    assert create.status_code == 403

    # Owner creates a patch; viewer cannot apply it.
    patch = (
        await owner.post(
            f"/projects/{project_id}/workspace/patches",
            json={
                "summary": "x",
                "files": [{"path": "f.txt", "change_type": "create", "new_content": "x"}],
            },
            headers=csrf_headers(owner),
        )
    ).json()
    apply = await viewer.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(viewer),
    )
    assert apply.status_code == 403


async def test_researcher_can_create_and_apply(make_client) -> None:
    owner = make_client()
    researcher = make_client()
    await register(owner, email="ide-owner2@example.com")
    await register(researcher, email="ide-res@example.com")
    org_id, project_id = await _org_project(owner)
    await _add_member(owner, org_id, project_id, "ide-res@example.com", "researcher")

    patch = (
        await researcher.post(
            f"/projects/{project_id}/workspace/patches",
            json={
                "summary": "x",
                "files": [{"path": "g.txt", "change_type": "create", "new_content": "g"}],
            },
            headers=csrf_headers(researcher),
        )
    ).json()
    apply = await researcher.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(researcher),
    )
    assert apply.status_code == 200
    assert apply.json()["status"] == "applied"
