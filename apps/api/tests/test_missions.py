"""Durable Research Mission workflow tests."""

from __future__ import annotations

from httpx import AsyncClient

from .helpers import csrf_headers, register


async def _org_id(client: AsyncClient) -> str:
    return (await client.get("/organizations")).json()[0]["id"]


async def _project(client: AsyncClient, name: str = "Mission Project") -> dict:
    response = await client.post(
        "/projects",
        json={"organization_id": await _org_id(client), "name": name},
        headers=csrf_headers(client),
    )
    response.raise_for_status()
    return response.json()


async def _mission(client: AsyncClient, project_id: str) -> dict:
    response = await client.post(
        f"/projects/{project_id}/missions",
        json={
            "topic": "弱监督医学图像分割中的不确定性建模",
            "objective": "形成综述并设计可复现实验",
            "field": "Medical AI",
            "scope": {"years": [2021, 2026], "minimum_papers": 8},
        },
        headers=csrf_headers(client),
    )
    response.raise_for_status()
    return response.json()


async def test_create_mission_initializes_five_step_workflow(client: AsyncClient) -> None:
    await register(client, email="mission-create@example.com")
    project = await _project(client)
    mission = await _mission(client, project["id"])

    assert mission["status"] == "draft"
    assert mission["current_step"] == "scope"
    assert mission["progress"] == 0
    assert [step["step_kind"] for step in mission["steps"]] == [
        "scope",
        "literature",
        "reading",
        "review",
        "experiment_plan",
    ]
    assert mission["steps"][0]["status"] == "ready"
    assert all(step["status"] == "locked" for step in mission["steps"][1:])

    page = (await client.get(f"/projects/{project['id']}/missions")).json()
    assert page["total"] == 1
    assert page["items"][0]["topic"] == mission["topic"]


async def test_mission_update_uses_optimistic_version(client: AsyncClient) -> None:
    await register(client, email="mission-version@example.com")
    project = await _project(client)
    mission = await _mission(client, project["id"])

    updated = await client.patch(
        f"/projects/{project['id']}/missions/{mission['id']}",
        json={
            "expected_version": mission["version"],
            "scope": {"years": [2020, 2026], "minimum_papers": 10},
            "status": "active",
        },
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == mission["version"] + 1
    assert updated.json()["scope_json"]["minimum_papers"] == 10

    stale = await client.patch(
        f"/projects/{project['id']}/missions/{mission['id']}",
        json={"expected_version": mission["version"], "objective": "stale write"},
        headers=csrf_headers(client),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "mission_version_conflict"


async def test_approve_step_unlocks_next_step_and_writes_timeline(
    client: AsyncClient,
) -> None:
    await register(client, email="mission-step@example.com")
    project = await _project(client)
    mission = await _mission(client, project["id"])
    scope = mission["steps"][0]

    edited = await client.put(
        f"/projects/{project['id']}/missions/{mission['id']}/steps/scope",
        json={
            "expected_version": scope["version"],
            "input": {"keywords": ["weak supervision", "uncertainty"]},
            "output": {"inclusion": ["peer reviewed", "2021-2026"]},
            "status": "needs_review",
        },
        headers=csrf_headers(client),
    )
    assert edited.status_code == 200
    edited_scope = edited.json()["steps"][0]
    assert edited_scope["status"] == "needs_review"

    approved = await client.post(
        f"/projects/{project['id']}/missions/{mission['id']}/steps/scope/approve",
        json={"expected_version": edited_scope["version"], "note": "范围已确认"},
        headers=csrf_headers(client),
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["current_step"] == "literature"
    assert body["progress"] == 20
    assert body["steps"][0]["status"] == "completed"
    assert body["steps"][1]["status"] == "ready"

    timeline = (
        await client.get(
            f"/projects/{project['id']}/missions/{mission['id']}/timeline"
        )
    ).json()
    assert timeline["total"] == 3
    assert timeline["items"][0]["event_type"] == "mission.step.approved"
    assert timeline["items"][0]["payload_json"]["note"] == "范围已确认"


async def test_mission_is_hidden_from_other_tenants(make_client) -> None:
    owner = make_client()
    outsider = make_client()
    await register(owner, email="mission-owner@example.com")
    await register(outsider, email="mission-outsider@example.com")
    project = await _project(owner)
    mission = await _mission(owner, project["id"])

    response = await outsider.get(
        f"/projects/{project['id']}/missions/{mission['id']}"
    )
    assert response.status_code == 404
