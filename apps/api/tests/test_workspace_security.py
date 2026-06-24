"""Workspace path-guard and deny-list security tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from researchos.common.config import get_settings
from researchos.common.paths import WorkspaceAccessError, resolve_in_workspace
from researchos.workspace import fs

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


def _ws_dir(project_id: str) -> Path:
    return Path(get_settings().workspace_root) / project_id


async def test_path_traversal_rejected(client) -> None:
    project_id = await _make_project(client, "ws1@example.com")
    resp = await client.get(
        f"/projects/{project_id}/workspace/files", params={"path": "../../etc/passwd"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "workspace_forbidden"


async def test_absolute_path_rejected(client) -> None:
    project_id = await _make_project(client, "ws2@example.com")
    resp = await client.get(
        f"/projects/{project_id}/workspace/files", params={"path": "/etc/hosts"}
    )
    assert resp.status_code == 403


async def test_denied_file_read_returns_403(client) -> None:
    project_id = await _make_project(client, "ws3@example.com")
    ws = _ws_dir(project_id)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / ".env").write_text("SECRET=1\n", encoding="utf-8")

    resp = await client.get(f"/projects/{project_id}/workspace/files", params={"path": ".env"})
    assert resp.status_code == 403


async def test_tree_hides_denied_files(client) -> None:
    project_id = await _make_project(client, "ws4@example.com")
    ws = _ws_dir(project_id)
    (ws / "src").mkdir(parents=True, exist_ok=True)
    (ws / "README.md").write_text("# hi\n", encoding="utf-8")
    (ws / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ws / "server.key").write_text("KEY\n", encoding="utf-8")
    (ws / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    tree = (await client.get(f"/projects/{project_id}/workspace/tree")).json()

    def names(nodes):
        out = []
        for n in nodes:
            out.append(n["name"])
            out.extend(names(n.get("children", [])))
        return out

    listed = names(tree["nodes"])
    assert "README.md" in listed
    assert "main.py" in listed
    assert ".env" not in listed
    assert "server.key" not in listed


def test_symlink_escape_rejected() -> None:
    project_id = str(uuid.uuid4())
    ws = _ws_dir(project_id)
    ws.mkdir(parents=True, exist_ok=True)
    outside = Path(get_settings().workspace_root) / "OUTSIDE_SECRET.txt"
    outside.write_text("secret\n", encoding="utf-8")
    link = ws / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")

    # Resolving through the symlink escapes the root -> rejected.
    with pytest.raises(WorkspaceAccessError):
        resolve_in_workspace(project_id, "escape")

    # And the tree never lists it.
    nodes = fs.build_tree(uuid.UUID(project_id))
    assert all(n["name"] != "escape" for n in nodes)
