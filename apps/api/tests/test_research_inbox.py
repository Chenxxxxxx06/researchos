"""Research Inbox persistence and analysis-dispatch tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _make_project(client) -> str:
    await register(client, email="inbox-owner@example.com")
    org_id = (await client.get("/organizations")).json()[0]["id"]
    response = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Inbox project"},
        headers=csrf_headers(client),
    )
    return response.json()["id"]


async def test_create_list_and_analyze_inbox_item(client) -> None:
    project_id = await _make_project(client)
    created = await client.post(
        f"/projects/{project_id}/inbox",
        json={
            "source_type": "message",
            "sender": "Advisor",
            "title": "Try a stronger baseline",
            "content_text": "Compare against method A and report three seeds.",
        },
        headers=csrf_headers(client),
    )
    assert created.status_code == 201
    item = created.json()
    assert item["agent_run_id"] is None

    listing = await client.get(f"/projects/{project_id}/inbox")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()] == [item["id"]]

    analyzed = await client.post(
        f"/projects/{project_id}/inbox/{item['id']}/analyze",
        json={"mode": "meeting_summary"},
        headers=csrf_headers(client),
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["status"] == "queued"

    refreshed = (await client.get(f"/projects/{project_id}/inbox")).json()[0]
    assert refreshed["agent_run_id"] == analyzed.json()["agent_run_id"]


async def test_upload_markdown_extracts_and_dispatches_analysis(client) -> None:
    project_id = await _make_project(client)
    response = await client.post(
        f"/projects/{project_id}/inbox/upload",
        files={"file": ("meeting.md", b"# Decision\nRun three seeds.", "text/markdown")},
        data={
            "sender": "Advisor",
            "title": "Weekly meeting",
            "analysis_mode": "meeting_summary",
            "auto_analyze": "true",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["item"]["content_text"] == "# Decision\nRun three seeds."
    assert payload["item"]["source_type"] == "file"
    assert payload["analysis"]["status"] == "queued"
    listing = (await client.get(f"/projects/{project_id}/inbox")).json()
    assert listing[0]["agent_run_id"] == payload["analysis"]["agent_run_id"]
