"""Release Studio integration contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx

from researchos.common.secrets import encrypt_secret
from researchos.llm_config.models import LLMProviderConfig
from researchos.releases.models import ReleaseGenerationJob
from researchos.releases.schemas import CreateReleaseJobRequest
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


async def test_release_health_distinguishes_reachable_service_from_project_credentials(
    client, monkeypatch
) -> None:
    project_id = await _project(client, "release-health@example.com")

    class FakeHealthClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(
                200,
                json={"status": "needs_setup", "needs_setup": True},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(ReleaseService, "_client", lambda self, timeout: FakeHealthClient())
    response = await client.get(f"/projects/{project_id}/releases/integration")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert "按请求注入" in body["message"]


async def test_autodesign_start_forwards_qwen_to_every_supported_text_role(db_session) -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"run_id": "real-contract-run"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as external:
        service = ReleaseService(db_session, http_client=external)
        config = LLMProviderConfig(
            project_id=uuid.uuid4(),
            name="Qwen",
            provider_type="openai_compatible",
            base_url="https://dashscope.example/v1",
            model="qwen-plus",
            api_key=encrypt_secret("test-key"),
            is_active=True,
        )
        job = ReleaseGenerationJob(
            id=uuid.uuid4(),
            project_id=config.project_id,
            created_by=uuid.uuid4(),
            kind="website",
            engine="autodesign",
            model="qwen-plus",
            status="queued",
            story_pack="verified evidence " * 20,
            progress_json={},
        )
        payload = CreateReleaseJobRequest(
            kind="website",
            story_pack="verified evidence " * 20,
        )
        await service._start_external(job, config, payload)

    assert job.external_run_id == "real-contract-run"
    assert job.status == "running"
    for role in (
        "designer",
        "planner",
        "enhancer",
        "claim-graph",
        "deck-outline",
        "paper-memory",
        "critic",
        "composer",
        "ingest",
    ):
        assert captured[f"x-model-{role}"] == "qwen-plus"
    assert captured["x-openai-key"] == "test-key"
    assert captured["x-custom-openai-base"] == "https://dashscope.example/v1"


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
