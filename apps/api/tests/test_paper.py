"""Paper (LaTeX) workspace API tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_latex_project_save_and_compile(client) -> None:
    p = await _project(client, "paper@example.com")
    h = csrf_headers(client)

    lp = (
        await client.post(f"/projects/{p}/latex-projects", json={"name": "Paper"}, headers=h)
    ).json()

    # main.tex auto-created.
    files = (await client.get(f"/projects/{p}/latex-projects/{lp['id']}/files")).json()
    assert any(f["path"] == "main.tex" for f in files)

    # Save edited content.
    saved = await client.put(
        f"/projects/{p}/latex-projects/{lp['id']}/files",
        json={"path": "main.tex", "content": "\\section{Intro}\nHello world."},
        headers=h,
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == 2

    # Mock compile produces a preview (no shell).
    job = await client.post(f"/projects/{p}/latex-projects/{lp['id']}/compile", headers=h)
    assert job.status_code == 201
    body = job.json()
    assert body["status"] == "succeeded"
    assert "Hello world." in (body["preview"] or "")


async def test_paper_tenant_isolation(make_client) -> None:
    a = make_client()
    b = make_client()
    p = await _project(a, "paper-a@example.com")
    await register(b, email="paper-b@example.com")
    assert (await b.get(f"/projects/{p}/latex-projects")).status_code == 404
