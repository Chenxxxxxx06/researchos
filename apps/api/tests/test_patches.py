"""Patch proposal create / apply / conflict / reject tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _create_patch(client, project_id: str, files: list[dict], summary: str = "p") -> dict:
    resp = await client.post(
        f"/projects/{project_id}/workspace/patches",
        json={"summary": summary, "files": files},
        headers=csrf_headers(client),
    )
    resp.raise_for_status()
    return resp.json()


async def test_create_and_apply_patch_changes_file(client) -> None:
    project_id = await _make_project(client, "pa1@example.com")
    patch = await _create_patch(
        client,
        project_id,
        [{"path": "README.md", "change_type": "create", "new_content": "# Hello\n"}],
    )
    assert patch["status"] == "pending"

    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    assert apply.status_code == 200
    assert apply.json()["status"] == "applied"

    # File now exists with the proposed content.
    f = await client.get(f"/projects/{project_id}/workspace/files", params={"path": "README.md"})
    assert f.status_code == 200
    assert f.json()["content"] == "# Hello\n"


async def test_apply_conflict_does_not_write(client) -> None:
    project_id = await _make_project(client, "pa2@example.com")
    # Seed a file via an applied create.
    p1 = await _create_patch(
        client,
        project_id,
        [{"path": "a.txt", "change_type": "create", "new_content": "v1\n"}],
    )
    await client.post(
        f"/projects/{project_id}/workspace/patches/{p1['id']}/apply", headers=csrf_headers(client)
    )

    # Propose a modify with a wrong base_sha -> conflict.
    p2 = await _create_patch(
        client,
        project_id,
        [
            {
                "path": "a.txt",
                "change_type": "modify",
                "base_sha": "deadbeef" * 8,
                "new_content": "v2\n",
            }
        ],
    )
    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{p2['id']}/apply", headers=csrf_headers(client)
    )
    assert apply.status_code == 200
    body = apply.json()
    assert body["status"] == "conflict"
    assert body["conflicts"][0]["path"] == "a.txt"

    # File content is unchanged.
    f = await client.get(f"/projects/{project_id}/workspace/files", params={"path": "a.txt"})
    assert f.json()["content"] == "v1\n"


async def test_reject_patch(client) -> None:
    project_id = await _make_project(client, "pa3@example.com")
    patch = await _create_patch(
        client,
        project_id,
        [{"path": "b.txt", "change_type": "create", "new_content": "x\n"}],
    )
    resp = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/reject",
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


async def test_cannot_patch_denied_path(client) -> None:
    project_id = await _make_project(client, "pa4@example.com")
    resp = await client.post(
        f"/projects/{project_id}/workspace/patches",
        json={
            "summary": "x",
            "files": [{"path": ".env", "change_type": "create", "new_content": "S=1"}],
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 403
