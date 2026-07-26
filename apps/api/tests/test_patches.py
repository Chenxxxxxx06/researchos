"""Patch proposal create / apply / conflict / reject tests."""

from __future__ import annotations

import shutil
import uuid

import pytest

from researchos.common.config import get_settings
from researchos.git.runner import git_available
from researchos.workspace import fs

from .helpers import csrf_headers, register

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git binary not installed")


@pytest.fixture(autouse=True)
def _fresh_git_cache():
    # git_available is lru-cached; tests in other modules may flip the setting.
    git_available.cache_clear()
    yield
    git_available.cache_clear()


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _file_sha(client, project_id: str, path: str) -> str:
    resp = await client.get(
        f"/projects/{project_id}/workspace/files", params={"path": path}
    )
    resp.raise_for_status()
    return resp.json()["sha"]


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


async def test_modify_without_base_sha_is_422(client) -> None:
    project_id = await _make_project(client, "pa5@example.com")
    resp = await client.post(
        f"/projects/{project_id}/workspace/patches",
        json={
            "summary": "x",
            "files": [{"path": "f.txt", "change_type": "modify", "new_content": "y\n"}],
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422  # schema boundary closes the None==None hole


async def test_edits_patch_materializes_snapshots_and_hunks(client) -> None:
    project_id = await _make_project(client, "pa6@example.com")
    base = "def util():\n    return 1\n\nprint('x')\n"
    fs.write_file(uuid.UUID(project_id), "util.py", base)
    sha = await _file_sha(client, project_id, "util.py")

    patch = await _create_patch(
        client,
        project_id,
        [
            {
                "path": "util.py",
                "change_type": "modify",
                "base_sha": sha,
                "edits": [{"search": "    return 1\n", "replace": "    return 2\n"}],
            }
        ],
    )
    f = patch["files"][0]
    assert f["new_content"] == base.replace("return 1", "return 2")  # server-materialized
    assert f["base_content"] == base  # pre-image snapshot
    assert f["edits"] == [{"search": "    return 1\n", "replace": "    return 2\n"}]
    assert f["hunks"], "server must derive real diff hunks"
    assert any("+    return 2" in h["content"] for h in f["hunks"])

    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    assert apply.status_code == 200
    body = apply.json()
    assert body["status"] == "applied"
    assert "applied_commit_sha" in body
    got = await client.get(
        f"/projects/{project_id}/workspace/files", params={"path": "util.py"}
    )
    assert got.json()["content"] == base.replace("return 1", "return 2")


async def test_edits_with_stale_base_sha_fail_base_changed(client) -> None:
    project_id = await _make_project(client, "pa7@example.com")
    fs.write_file(uuid.UUID(project_id), "s.txt", "one\ntwo\n")

    resp = await client.post(
        f"/projects/{project_id}/workspace/patches",
        json={
            "summary": "stale",
            "files": [
                {
                    "path": "s.txt",
                    "change_type": "modify",
                    "base_sha": "0" * 64,
                    "edits": [{"search": "two\n", "replace": "TWO\n"}],
                }
            ],
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"]["files"][0]["reason"] == "base_changed"


async def test_ambiguous_edit_fails_per_file(client) -> None:
    project_id = await _make_project(client, "pa8@example.com")
    fs.write_file(uuid.UUID(project_id), "dup.txt", "dup\ndup\n")
    sha = await _file_sha(client, project_id, "dup.txt")

    resp = await client.post(
        f"/projects/{project_id}/workspace/patches",
        json={
            "summary": "amb",
            "files": [
                {
                    "path": "dup.txt",
                    "change_type": "modify",
                    "base_sha": sha,
                    "edits": [{"search": "dup\n", "replace": "DUP\n"}],
                }
            ],
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400
    failures = resp.json()["error"]["details"]["files"]
    assert failures[0]["reason"] == "ambiguous"
    assert failures[0]["index"] == 0


async def test_apply_conflict_on_missing_file_persists_and_reject(client) -> None:
    project_id = await _make_project(client, "pa9@example.com")
    fs.write_file(uuid.UUID(project_id), "gone.txt", "v1\n")
    sha = await _file_sha(client, project_id, "gone.txt")
    patch = await _create_patch(
        client,
        project_id,
        [
            {
                "path": "gone.txt",
                "change_type": "modify",
                "base_sha": sha,
                "new_content": "v2\n",
            }
        ],
    )
    fs.delete_file(uuid.UUID(project_id), "gone.txt")  # concurrent deletion

    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    body = apply.json()
    assert body["status"] == "conflict"  # MODIFY of a missing file conflicts
    assert body["conflicts"][0]["reason"] == "file missing"
    assert body["conflicts"][0]["actual_sha"] is None

    # Conflict details survive a refetch (persisted conflict_json).
    detail = (
        await client.get(f"/projects/{project_id}/workspace/patches/{patch['id']}")
    ).json()
    assert detail["status"] == "conflict"
    assert detail["conflicts"][0]["path"] == "gone.txt"

    # CONFLICT is no longer a dead end: reject is legal.
    rejected = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/reject",
        headers=csrf_headers(client),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


async def test_delete_of_missing_file_is_satisfied_noop(client) -> None:
    project_id = await _make_project(client, "pa10@example.com")
    fs.write_file(uuid.UUID(project_id), "d.txt", "bye\n")
    sha = await _file_sha(client, project_id, "d.txt")
    patch = await _create_patch(
        client,
        project_id,
        [{"path": "d.txt", "change_type": "delete", "base_sha": sha}],
    )
    fs.delete_file(uuid.UUID(project_id), "d.txt")  # already gone before apply

    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    body = apply.json()
    assert body["status"] == "applied"  # idempotent delete, not a conflict
    assert body["conflicts"] == []


async def test_partial_apply_by_paths_and_unknown_path(client) -> None:
    project_id = await _make_project(client, "pa11@example.com")
    patch = await _create_patch(
        client,
        project_id,
        [
            {"path": "one.txt", "change_type": "create", "new_content": "1\n"},
            {"path": "two.txt", "change_type": "create", "new_content": "2\n"},
        ],
    )

    unknown = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        json={"paths": ["nope.txt"]},
        headers=csrf_headers(client),
    )
    assert unknown.status_code == 400
    assert unknown.json()["error"]["details"]["unknown_paths"] == ["nope.txt"]

    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        json={"paths": ["one.txt"]},
        headers=csrf_headers(client),
    )
    body = apply.json()
    assert body["status"] == "applied"
    assert body["skipped_paths"] == ["two.txt"]
    assert (
        await client.get(
            f"/projects/{project_id}/workspace/files", params={"path": "one.txt"}
        )
    ).status_code == 200
    assert (
        await client.get(
            f"/projects/{project_id}/workspace/files", params={"path": "two.txt"}
        )
    ).status_code == 404


async def test_apply_with_git_disabled_returns_null_commit_sha(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "pa12@example.com")
    monkeypatch.setattr(get_settings(), "git_enabled", False)
    git_available.cache_clear()

    patch = await _create_patch(
        client,
        project_id,
        [{"path": "nogit.txt", "change_type": "create", "new_content": "x\n"}],
    )
    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    body = apply.json()
    assert body["status"] == "applied"  # apply works fine without git
    assert body["applied_commit_sha"] is None


@needs_git
async def test_apply_records_commit_sha_when_git_available(client) -> None:
    project_id = await _make_project(client, "pa13@example.com")
    patch = await _create_patch(
        client,
        project_id,
        [{"path": "tracked.txt", "change_type": "create", "new_content": "t\n"}],
    )
    apply = await client.post(
        f"/projects/{project_id}/workspace/patches/{patch['id']}/apply",
        headers=csrf_headers(client),
    )
    body = apply.json()
    assert body["status"] == "applied"
    assert body["applied_commit_sha"] and len(body["applied_commit_sha"]) == 40

    # The commit sha is persisted on the proposal too.
    detail = (
        await client.get(f"/projects/{project_id}/workspace/patches/{patch['id']}")
    ).json()
    assert detail["applied_commit_sha"] == body["applied_commit_sha"]
