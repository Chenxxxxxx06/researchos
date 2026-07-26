"""CAS save, revisions, merge-hint 409s, and path validation (DB, CI)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.documents.repository import DocumentFileRepository
from researchos.documents.service import _DEFAULT_MAIN, DocumentService
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService

from .helpers import csrf_headers, register


async def _paper_project(client, email: str) -> tuple[str, str]:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    h = csrf_headers(client)
    project_id = (
        await client.post("/projects", json={"organization_id": org_id, "name": "P"}, headers=h)
    ).json()["id"]
    lp = (
        await client.post(
            f"/projects/{project_id}/latex-projects", json={"name": "Paper"}, headers=h
        )
    ).json()
    return project_id, lp["id"]


def _files_url(p: str, lp: str) -> str:
    return f"/projects/{p}/latex-projects/{lp}/files"


async def test_cas_save_bumps_version_and_records_revision(client) -> None:
    p, lp = await _paper_project(client, "ver-cas@example.com")
    h = csrf_headers(client)

    saved = await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": "v2 content", "expected_version": 1},
        headers=h,
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == 2

    history = (await client.get(f"{_files_url(p, lp)}/history?path=main.tex")).json()
    assert [r["version"] for r in history] == [2, 1]

    rev1 = await client.get(f"{_files_url(p, lp)}/revision?path=main.tex&version=1")
    assert rev1.status_code == 200
    assert rev1.json()["content"] == _DEFAULT_MAIN
    assert rev1.json()["version"] == 1


async def test_stale_save_conflict_with_clean_merge_hint(client) -> None:
    p, lp = await _paper_project(client, "ver-merge@example.com")
    h = csrf_headers(client)

    server_edit = _DEFAULT_MAIN.replace("Write your introduction here.", "SERVER INTRO.")
    ok = await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": server_edit, "expected_version": 1},
        headers=h,
    )
    assert ok.status_code == 200

    # Client is still on v1 and edits a DIFFERENT line -> clean merge hint.
    client_edit = _DEFAULT_MAIN.replace("Present your results.", "CLIENT RESULTS.")
    stale = await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": client_edit, "expected_version": 1},
        headers=h,
    )
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "document_version_conflict"
    details = error["details"]
    assert details["path"] == "main.tex"
    assert details["expected_version"] == 1
    assert details["current_version"] == 2
    assert details["server_content"] == server_edit
    assert details["server_content_omitted"] is False
    assert details["base_available"] is True
    merge = details["merge"]
    assert merge["clean"] is True
    assert merge["conflicts"] == []
    assert "SERVER INTRO." in merge["merged_content"]
    assert "CLIENT RESULTS." in merge["merged_content"]


async def test_stale_save_conflict_with_overlapping_edits(client) -> None:
    p, lp = await _paper_project(client, "ver-conflict@example.com")
    h = csrf_headers(client)

    server_edit = _DEFAULT_MAIN.replace("Write your introduction here.", "SERVER LINE.")
    await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": server_edit, "expected_version": 1},
        headers=h,
    )
    client_edit = _DEFAULT_MAIN.replace("Write your introduction here.", "CLIENT LINE.")
    stale = await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": client_edit, "expected_version": 1},
        headers=h,
    )
    assert stale.status_code == 409
    merge = stale.json()["error"]["details"]["merge"]
    assert merge["clean"] is False
    assert merge["merged_content"] is None
    assert len(merge["conflicts"]) == 1
    conflict = merge["conflicts"][0]
    assert {"base_start", "base_end", "base_text", "server_text", "client_text"} <= set(conflict)
    assert "SERVER LINE." in conflict["server_text"]
    assert "CLIENT LINE." in conflict["client_text"]


async def test_omitted_expected_version_force_saves(client) -> None:
    p, lp = await _paper_project(client, "ver-force@example.com")
    h = csrf_headers(client)

    await client.put(
        _files_url(p, lp),
        json={"path": "main.tex", "content": "second", "expected_version": 1},
        headers=h,
    )
    # Legacy client without expected_version: still last-write-wins.
    forced = await client.put(
        _files_url(p, lp), json={"path": "main.tex", "content": "third"}, headers=h
    )
    assert forced.status_code == 200
    assert forced.json()["version"] == 3
    assert forced.json()["content"] == "third"


async def test_path_traversal_and_bad_paths_rejected(client) -> None:
    p, lp = await _paper_project(client, "ver-path@example.com")
    h = csrf_headers(client)

    for bad in ["../evil.tex", "/abs.tex", "a\\b.tex", "a/../b.tex", "a//b.tex"]:
        resp = await client.put(
            _files_url(p, lp), json={"path": bad, "content": "x"}, headers=h
        )
        assert resp.status_code == 422, bad
        assert resp.json()["error"]["code"] == "validation_error"


async def test_concurrent_create_race_resolves_to_update(
    db_session: AsyncSession, monkeypatch
) -> None:
    """A lost create race (unique violation) falls through to the update path."""

    user, org = await AuthService(db_session).register(
        email="ver-race@example.com", password="password123", display_name="R"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    svc = DocumentService(db_session)
    lp = await svc.create_latex_project(user, project.id, name="Paper")

    real_get_by_path = DocumentFileRepository.get_by_path
    calls = {"n": 0}

    async def flaky_get_by_path(self, latex_project_id, path):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # simulate: another writer created the row after our check
        return await real_get_by_path(self, latex_project_id, path)

    monkeypatch.setattr(DocumentFileRepository, "get_by_path", flaky_get_by_path)
    file = await svc.save_file(
        user, project.id, lp.id, path="main.tex", content="raced content"
    )
    assert file.version == 2
    assert file.content == "raced content"
    assert calls["n"] >= 2


async def test_revisions_pruned_to_keep_limit(db_session: AsyncSession) -> None:
    user, org = await AuthService(db_session).register(
        email="ver-prune@example.com", password="password123", display_name="R"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    svc = DocumentService(db_session)
    lp = await svc.create_latex_project(user, project.id, name="Paper")

    for i in range(55):
        await svc.write_file_versioned(user, lp.id, path="main.tex", content=f"content {i}")
    await db_session.commit()

    revisions = await svc.revisions.list_versions(
        (await svc.files.get_by_path(lp.id, "main.tex")).id, limit=200
    )
    versions = [r.version for r in revisions]
    assert len(versions) == 50
    assert max(versions) == 56  # v1 create + 55 writes
    assert min(versions) == 7  # oldest 6 pruned


async def test_missing_revision_returns_404(client) -> None:
    p, lp = await _paper_project(client, "ver-miss@example.com")
    resp = await client.get(f"{_files_url(p, lp)}/revision?path=main.tex&version=99")
    assert resp.status_code == 404
