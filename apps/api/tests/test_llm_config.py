"""Integration tests for per-project LLM provider configuration management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from researchos.common.secrets import decrypt_secret
from researchos.llm_config.models import LLMProviderConfig

from .helpers import csrf_headers, register


async def _make_project(client: AsyncClient, email: str) -> str:
    await register(client, email=email)
    organization_id = (await client.get("/organizations")).json()[0]["id"]
    response = await client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "LLM project"},
        headers=csrf_headers(client),
    )
    response.raise_for_status()
    return response.json()["id"]


async def _create_config(
    client: AsyncClient,
    project_id: str,
    *,
    name: str = "default",
    model: str = "model-a",
    api_key: str = "test-secret",
) -> object:
    return await client.post(
        f"/projects/{project_id}/settings/llm",
        json={
            "name": name,
            "provider_type": "openai_compatible",
            "base_url": "https://example.test/v1/",
            "model": model,
            "api_key": api_key,
            "is_active": True,
            "description": "test configuration",
        },
        headers=csrf_headers(client),
    )


async def test_create_same_name_creates_distinct_rows(client) -> None:
    project_id = await _make_project(client, "llm-create@example.com")
    first = await _create_config(client, project_id, name="shared", model="model-a")
    second = await _create_config(client, project_id, name="shared", model="model-b")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]


async def test_patch_updates_by_id_and_empty_key_preserves_secret(client, db_session) -> None:
    project_id = await _make_project(client, "llm-edit@example.com")
    created = await _create_config(client, project_id, api_key="original-secret")
    config_id = created.json()["id"]
    response = await client.patch(
        f"/projects/{project_id}/settings/llm/{config_id}",
        json={
            "name": "renamed",
            "provider_type": "openai_compatible",
            "base_url": "https://example.test/v1/",
            "model": "model-b",
            "api_key": "",
            "is_active": False,
            "description": "edited",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "renamed"
    assert response.json()["base_url"] == "https://example.test/v1"
    assert response.json()["is_active"] is False
    row = await db_session.get(LLMProviderConfig, uuid.UUID(config_id))
    assert decrypt_secret(row.api_key) == "original-secret"


async def test_patch_non_empty_key_replaces_secret(client, db_session) -> None:
    project_id = await _make_project(client, "llm-replace@example.com")
    created = await _create_config(client, project_id, api_key="original-secret")
    config_id = created.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}/settings/llm/{config_id}",
        json={"api_key": "replacement-secret"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    row = await db_session.get(LLMProviderConfig, uuid.UUID(config_id))
    assert decrypt_secret(row.api_key) == "replacement-secret"


async def test_patch_omitted_fields_preserve_existing_values(client, db_session) -> None:
    project_id = await _make_project(client, "llm-partial@example.com")
    created = await _create_config(client, project_id, name="keep-me", model="model-a")
    config_id = created.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}/settings/llm/{config_id}",
        json={"description": "description-only update"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "keep-me"
    assert response.json()["model"] == "model-a"
    assert response.json()["base_url"] == "https://example.test/v1"
    assert response.json()["is_active"] is True
    assert response.json()["description"] == "description-only update"


async def test_patch_rejects_null_for_required_fields(client) -> None:
    project_id = await _make_project(client, "llm-null@example.com")
    created = await _create_config(client, project_id)

    response = await client.patch(
        f"/projects/{project_id}/settings/llm/{created.json()['id']}",
        json={"model": None},
        headers=csrf_headers(client),
    )

    assert response.status_code == 422


async def test_patch_cross_project_config_returns_404(client) -> None:
    project_id = await _make_project(client, "llm-cross@example.com")
    other_project_response = await client.post(
        "/projects",
        json={
            "organization_id": (await client.get("/organizations")).json()[0]["id"],
            "name": "Other project",
        },
        headers=csrf_headers(client),
    )
    other_project_response.raise_for_status()
    created = await _create_config(client, project_id)

    response = await client.patch(
        f"/projects/{other_project_response.json()['id']}/settings/llm/{created.json()['id']}",
        json={"name": "hidden"},
        headers=csrf_headers(client),
    )

    assert response.status_code == 404


async def test_viewer_cannot_patch_config(make_client) -> None:
    owner = make_client()
    viewer = make_client()
    await register(owner, email="llm-owner@example.com")
    await register(viewer, email="llm-viewer@example.com")
    organization_id = (await owner.get("/organizations")).json()[0]["id"]
    project_response = await owner.post(
        "/projects",
        json={"organization_id": organization_id, "name": "LLM project"},
        headers=csrf_headers(owner),
    )
    project_response.raise_for_status()
    project_id = project_response.json()["id"]
    await owner.post(
        f"/organizations/{organization_id}/members",
        json={"email": "llm-viewer@example.com", "role": "member"},
        headers=csrf_headers(owner),
    )
    await owner.post(
        f"/projects/{project_id}/members",
        json={"email": "llm-viewer@example.com", "role": "viewer"},
        headers=csrf_headers(owner),
    )
    created = await _create_config(owner, project_id)

    response = await viewer.patch(
        f"/projects/{project_id}/settings/llm/{created.json()['id']}",
        json={"name": "forbidden"},
        headers=csrf_headers(viewer),
    )

    assert response.status_code == 403


async def test_list_configs_orders_most_recently_updated_first(client, db_session) -> None:
    project_id = await _make_project(client, "llm-order@example.com")
    older = await _create_config(client, project_id, name="older")
    newer = await _create_config(client, project_id, name="newer")
    older_row = await db_session.get(LLMProviderConfig, uuid.UUID(older.json()["id"]))
    newer_row = await db_session.get(LLMProviderConfig, uuid.UUID(newer.json()["id"]))
    older_row.updated_at = datetime.now(UTC) - timedelta(days=1)
    newer_row.updated_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(f"/projects/{project_id}/settings/llm")

    assert response.status_code == 200
    assert [config["id"] for config in response.json()] == [
        newer.json()["id"],
        older.json()["id"],
    ]
