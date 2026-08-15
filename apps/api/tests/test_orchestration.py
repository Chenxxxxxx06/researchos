"""Durable DAG bootstrap, gate, lease, and artifact flow."""

from .helpers import csrf_headers, register


async def _project_and_mission(client) -> tuple[str, str]:
    await register(client, email="orchestration@example.com")
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = await client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Agent Army"},
        headers=csrf_headers(client),
    )
    project_id = project.json()["id"]
    mission = await client.post(
        f"/projects/{project_id}/missions",
        json={"topic": "Reliable research agents", "objective": "Verify the full chain"},
        headers=csrf_headers(client),
    )
    return project_id, mission.json()["id"]


async def test_bootstrap_gate_lease_submit_and_promote(client) -> None:
    project_id, mission_id = await _project_and_mission(client)
    base = f"/projects/{project_id}/orchestration"
    bootstrapped = await client.post(
        f"{base}/missions/{mission_id}/bootstrap", headers=csrf_headers(client)
    )
    assert bootstrapped.status_code == 201
    graph = bootstrapped.json()
    assert len(graph["tasks"]) == 17
    assert graph["counts"]["waiting_approval"] == 1
    scope = next(task for task in graph["tasks"] if task["task_key"] == "scope")
    discover = next(task for task in graph["tasks"] if task["task_key"] == "discover")
    assert scope["status"] == "waiting_approval"
    assert discover["status"] == "draft"

    scope_gate = next(gate for gate in graph["gates"] if gate["gate_kind"] == "scope")
    decided = await client.post(
        f"{base}/gates/{scope_gate['id']}/decision",
        json={"decision": "approve", "note": "Scope reviewed"},
        headers=csrf_headers(client),
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "completed"

    ticked = await client.post(f"{base}/missions/{mission_id}/tick", headers=csrf_headers(client))
    assert ticked.status_code == 200
    discover = next(
        task for task in ticked.json()["graph"]["tasks"] if task["task_key"] == "discover"
    )
    assert discover["status"] == "ready"

    leased = await client.post(
        f"{base}/leases/next",
        json={"owner": "worker-test", "role": "evidence", "lease_seconds": 60},
        headers=csrf_headers(client),
    )
    assert leased.status_code == 200
    lease = leased.json()
    assert lease["task"]["task_key"] == "discover"
    token = lease["lease_token"]

    heartbeat = await client.post(
        f"{base}/leases/{token}/heartbeat",
        json={"lease_seconds": 60, "running": True},
        headers=csrf_headers(client),
    )
    assert heartbeat.status_code == 200

    submitted = await client.post(
        f"{base}/leases/{token}/submit",
        json={
            "output": {"papers": 12},
            "artifacts": [
                {
                    "schema_name": "paper-set/v1",
                    "content_hash": "a" * 64,
                    "metadata": {"papers": 12},
                }
            ],
        },
        headers=csrf_headers(client),
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "completed"

    ticked = await client.post(f"{base}/missions/{mission_id}/tick", headers=csrf_headers(client))
    read = next(task for task in ticked.json()["graph"]["tasks"] if task["task_key"] == "read")
    assert read["status"] == "ready"

    duplicate = await client.post(
        f"{base}/missions/{mission_id}/bootstrap", headers=csrf_headers(client)
    )
    assert duplicate.status_code == 201
    assert len(duplicate.json()["tasks"]) == 17
