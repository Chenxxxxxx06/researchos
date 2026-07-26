"""Mock compile: diagnostics, preview model, reachable FAILED, WS event (DB, CI)."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _paper_project(client, email: str) -> tuple[str, str]:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    h = csrf_headers(client)
    project_id = (
        await client.post("/projects", json={"organization_id": org_id, "name": "P"}, headers=h)
    ).json()["id"]
    lp_id = (
        await client.post(
            f"/projects/{project_id}/latex-projects", json={"name": "Paper"}, headers=h
        )
    ).json()["id"]
    return project_id, lp_id


def _base(p: str, lp: str) -> str:
    return f"/projects/{p}/latex-projects/{lp}"


async def test_default_template_compiles_clean(client) -> None:
    p, lp = await _paper_project(client, "cmp-clean@example.com")
    h = csrf_headers(client)

    resp = await client.post(f"{_base(p, lp)}/compile", headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["engine"] == "mock"
    assert body["diagnostics"] == []
    assert body["error_summary"] is None
    model = body["preview_model"]
    assert model["title"] == "Untitled Paper"
    assert [s["title"] for s in model["sections"]] == ["Introduction", "Method", "Results"]
    assert "Write your introduction here." in (body["preview"] or "")

    # GET returns the same enriched shape.
    job = (await client.get(f"{_base(p, lp)}/compile-jobs/{body['id']}")).json()
    assert job["status"] == "succeeded"
    assert job["diagnostics"] == []
    assert job["preview_model"]["title"] == "Untitled Paper"


async def test_broken_document_reaches_failed(client) -> None:
    p, lp = await _paper_project(client, "cmp-broken@example.com")
    h = csrf_headers(client)
    await client.put(
        f"{_base(p, lp)}/files",
        json={
            "path": "main.tex",
            "content": "\\documentclass{article}\n\\begin{document}\nText\n\\begin{figure}\n",
        },
        headers=h,
    )

    body = (await client.post(f"{_base(p, lp)}/compile", headers=h)).json()
    assert body["status"] == "failed"
    assert body["error_summary"]
    codes = {d["code"] for d in body["diagnostics"]}
    assert "unclosed_environment" in codes
    assert "missing_end_document" in codes
    assert all(d["severity"] in {"error", "warning"} for d in body["diagnostics"])
    assert any(d["severity"] == "error" for d in body["diagnostics"])


async def test_warnings_do_not_fail_compile(client) -> None:
    p, lp = await _paper_project(client, "cmp-warn@example.com")
    h = csrf_headers(client)
    await client.put(
        f"{_base(p, lp)}/files",
        json={
            "path": "main.tex",
            "content": (
                "\\documentclass{article}\n\\begin{document}\n"
                "As shown by \\cite{ghost2020}.\n\\end{document}\n"
            ),
        },
        headers=h,
    )

    body = (await client.post(f"{_base(p, lp)}/compile", headers=h)).json()
    assert body["status"] == "succeeded"
    warning = next(d for d in body["diagnostics"] if d["code"] == "undefined_citation")
    assert warning["severity"] == "warning"
    assert "ghost2020" in warning["message"]
    assert warning["file"] == "main.tex"
    assert warning["line"] == 3


async def test_compile_publishes_ws_event(client, monkeypatch) -> None:
    events: list[tuple[str, dict]] = []

    async def _record(project_id: str, envelope: dict) -> None:
        events.append((project_id, envelope))

    monkeypatch.setattr("researchos.documents.service.publish_event", _record)
    p, lp = await _paper_project(client, "cmp-event@example.com")
    h = csrf_headers(client)

    body = (await client.post(f"{_base(p, lp)}/compile", headers=h)).json()
    assert len(events) == 1
    project_id, envelope = events[0]
    assert project_id == p
    assert envelope["event_type"] == "latex.compile.completed"
    assert envelope["resource_type"] == "latex_compile"
    assert envelope["resource_id"] == body["id"]
    assert envelope["payload"] == {
        "job_id": body["id"],
        "status": "succeeded",
        "engine": "mock",
        "diagnostics_count": 0,
        "error_summary": None,
    }

    # A structurally broken document publishes the failed variant.
    await client.put(
        f"{_base(p, lp)}/files",
        json={"path": "main.tex", "content": "\\begin{document}\nText\n"},
        headers=h,
    )
    failed = (await client.post(f"{_base(p, lp)}/compile", headers=h)).json()
    assert failed["status"] == "failed"
    assert events[-1][1]["event_type"] == "latex.compile.failed"
    assert events[-1][1]["payload"]["error_summary"]
