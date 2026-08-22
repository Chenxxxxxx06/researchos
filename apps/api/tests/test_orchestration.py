"""Durable DAG bootstrap, gate, lease, and artifact flow."""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.identity.models import User
from researchos.orchestration.enums import MissionTaskStatus
from researchos.orchestration.models import MissionTask, TaskArtifact
from researchos.orchestration.service import OrchestrationService

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
    assert len(graph["tasks"]) == 26
    assert graph["counts"]["waiting_approval"] == 1
    assert graph["progress"]["total_tasks"] == 26
    assert graph["progress"]["current_phase"] == "scope"
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
    assert len(duplicate.json()["tasks"]) == 26

    capabilities = await client.get(f"/projects/{project_id}/agents/capabilities")
    assert capabilities.status_code == 200
    roles = {item["agent_type"] for item in capabilities.json()}
    assert {
        "idea_explorer",
        "benchmark",
        "leader",
        "viewer",
        "writer",
        "drawer",
        "progress",
    } <= roles

    autopilot = await client.post(
        f"{base}/missions/{mission_id}/autopilot",
        json={"venue": "neurips", "isolated_workspace_confirmed": True},
        headers=csrf_headers(client),
    )
    assert autopilot.status_code == 200
    assert autopilot.json()["state"] == "blocked"
    assert autopilot.json()["blockers"] == ["model_config_required"]


async def test_handoff_references_the_exact_canonical_artifact(client, db_session) -> None:
    project_id, mission_id = await _project_and_mission(client)
    headers = csrf_headers(client)
    base = f"/projects/{project_id}/orchestration"
    await client.post(f"{base}/missions/{mission_id}/bootstrap", headers=headers)
    task = await db_session.scalar(
        select(MissionTask).where(
            MissionTask.mission_id == uuid.UUID(mission_id),
            MissionTask.task_key == "discover",
        )
    )
    user = await db_session.scalar(select(User).where(User.email == "orchestration@example.com"))
    assert task is not None and user is not None
    task.status = MissionTaskStatus.RUNNING
    task.attempt = 1
    payload = {"message": "verified discovery", "citations": ["arxiv:2608.1"]}
    run = AgentRun(
        project_id=uuid.UUID(project_id),
        user_id=user.id,
        agent_type=AgentType.RESEARCH,
        status=AgentRunStatus.COMPLETED,
        input_json={"context": {"mission_task_id": str(task.id)}},
        output_json=payload,
        finished_at=datetime.now(tz=UTC),
    )
    db_session.add(run)
    await db_session.flush()
    assert await OrchestrationService(db_session).reconcile_run(run) is True
    await db_session.commit()

    artifacts = list(
        (await db_session.execute(select(TaskArtifact).where(TaskArtifact.task_id == task.id)))
        .scalars()
        .all()
    )
    canonical = next(item for item in artifacts if item.schema_name == "agent-run/research")
    handoff = next(item for item in artifacts if item.schema_name == "researchos.handoff/v1")
    expected_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    assert canonical.content_hash == expected_hash
    assert handoff.metadata_json["output"]["artifact_id"] == str(canonical.id)
    assert handoff.metadata_json["output"]["sha256"] == canonical.content_hash
    assert handoff.input_artifact_versions_json[0]["artifact_id"] == str(canonical.id)


async def test_research_loop_keeps_candidate_and_unlocks_downstream(client, db_session) -> None:
    project_id, mission_id = await _project_and_mission(client)
    headers = csrf_headers(client)
    base = f"/projects/{project_id}/orchestration"
    await client.post(f"{base}/missions/{mission_id}/bootstrap", headers=headers)
    task = await db_session.scalar(
        select(MissionTask).where(
            MissionTask.mission_id == uuid.UUID(mission_id),
            MissionTask.task_key == "experiment_run",
        )
    )
    assert task is not None
    task.status = MissionTaskStatus.READY
    await db_session.commit()

    experiment = (
        await client.post(
            f"/projects/{project_id}/experiments",
            json={"name": "Bounded optimizer"},
            headers=headers,
        )
    ).json()
    baseline = (
        await client.post(
            f"/projects/{project_id}/experiments/{experiment['id']}/runs",
            json={"name": "baseline", "status": "completed", "git_commit": "a" * 40},
            headers=headers,
        )
    ).json()
    await client.post(
        f"/projects/{project_id}/experiment-runs/{baseline['id']}/metrics",
        json={"points": [{"name": "val_loss", "step": 1, "value": 1.0}]},
        headers=headers,
    )
    created = await client.post(
        f"{base}/missions/{mission_id}/research-loops",
        json={
            "name": "Loss search",
            "metric_name": "val_loss",
            "metric_direction": "min",
            "baseline_run_id": baseline["id"],
            "fixed_budget_seconds": 300,
            "max_iterations": 1,
            "patience": 1,
            "min_delta": 0.01,
            "editable_scopes": ["src"],
            "protected_scopes": ["src/eval.py"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    loop = created.json()
    proposed = await client.post(
        f"{base}/research-loops/{loop['id']}/iterations",
        json={
            "hypothesis": "A smaller learning rate will stabilize validation loss.",
            "component": "optimizer.learning_rate",
            "expected_effect": "Reduce final validation loss without extra complexity.",
            "changed_paths": ["src/train.py"],
        },
        headers=headers,
    )
    assert proposed.status_code == 201
    iteration = proposed.json()["iterations"][0]
    candidate = (
        await client.post(
            f"/projects/{project_id}/experiments/{experiment['id']}/runs",
            json={
                "name": "candidate-1",
                "status": "completed",
                "git_commit": "b" * 40,
                "config": {"research_loop_iteration_id": iteration["id"]},
            },
            headers=headers,
        )
    ).json()
    await client.post(
        f"/projects/{project_id}/experiment-runs/{candidate['id']}/metrics",
        json={"points": [{"name": "val_loss", "step": 1, "value": 0.9}]},
        headers=headers,
    )
    evaluated = await client.post(
        f"{base}/research-iterations/{iteration['id']}/evaluate",
        json={
            "experiment_run_id": candidate["id"],
            "complexity_delta": 0,
            "critic_score": 0.9,
            "rule_checks": {"reproducible": True, "artifact_integrity": True},
        },
        headers=headers,
    )
    assert evaluated.status_code == 200
    result = evaluated.json()
    assert result["status"] == "completed"
    assert result["best_run_id"] == candidate["id"]
    assert result["best_metric_value"] == 0.9
    assert result["iterations"][0]["status"] == "kept"

    graph = (await client.get(f"{base}/missions/{mission_id}")).json()
    experiment_task = next(item for item in graph["tasks"] if item["task_key"] == "experiment_run")
    reproduce = next(item for item in graph["tasks"] if item["task_key"] == "reproduce")
    assert experiment_task["status"] == "completed"
    assert reproduce["status"] == "draft"  # progress-controller receipt is also required
