"""Release Studio integration contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from researchos.releases.service import ReleaseService

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    organization_id = (await client.get("/organizations")).json()[0]["id"]
    response = await client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Release project"},
        headers=csrf_headers(client),
    )
    return response.json()["id"]


async def _qwen_config(client, project_id: str) -> str:
    response = await client.post(
        f"/projects/{project_id}/settings/llm",
        json={
            "name": "Qwen release",
            "provider_type": "openai_compatible",
            "base_url": "https://dashscope.example/v1",
            "model": "qwen-plus",
            "api_key": "test-key",
            "is_active": True,
        },
        headers=csrf_headers(client),
    )
    response.raise_for_status()
    return response.json()["id"]


async def test_release_requires_active_qwen_plus(client) -> None:
    project_id = await _project(client, "release-missing-model@example.com")
    response = await client.post(
        f"/projects/{project_id}/releases",
        json={"kind": "poster", "story_pack": "grounded evidence " * 20},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "qwen_plus_required"


async def test_release_job_is_persisted_with_autodesign_run(client, monkeypatch) -> None:
    project_id = await _project(client, "release-job@example.com")
    await _qwen_config(client, project_id)

    async def fake_start(self, job, config, payload) -> None:
        assert config.model == "qwen-plus"
        assert payload.kind == "poster"
        job.external_run_id = "external-run-1"
        job.status = "running"
        job.started_at = datetime.now(tz=UTC)
        job.progress_json = {
            "phase": "running",
            "output_directory": "out/runs/external-run-1/final",
        }

    monkeypatch.setattr(ReleaseService, "_start_external", fake_start)
    created = await client.post(
        f"/projects/{project_id}/releases",
        json={"kind": "poster", "story_pack": "verified project evidence " * 20},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["engine"] == "autodesign"
    assert body["model"] == "qwen-plus"
    assert body["external_run_id"] == "external-run-1"
    assert body["status"] == "running"

    jobs = (await client.get(f"/projects/{project_id}/releases")).json()
    assert [item["id"] for item in jobs] == [body["id"]]
