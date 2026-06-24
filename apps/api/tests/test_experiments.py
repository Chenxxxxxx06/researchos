"""Experiment dashboard API tests."""

from __future__ import annotations

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_experiment_run_metrics_logs_artifacts(client) -> None:
    p = await _project(client, "exp@example.com")
    h = csrf_headers(client)

    exp = (await client.post(f"/projects/{p}/experiments", json={"name": "E1"}, headers=h)).json()
    run = (
        await client.post(
            f"/projects/{p}/experiments/{exp['id']}/runs",
            json={"name": "run-1", "status": "running"},
            headers=h,
        )
    ).json()

    rec = await client.post(
        f"/projects/{p}/experiment-runs/{run['id']}/metrics",
        json={
            "points": [
                {"name": "loss", "step": 0, "value": 1.0},
                {"name": "loss", "step": 1, "value": 0.5},
                {"name": "accuracy", "step": 1, "value": 0.8},
            ]
        },
        headers=h,
    )
    assert rec.status_code == 201
    metrics = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/metrics")).json()
    assert len(metrics) == 3

    log = await client.post(
        f"/projects/{p}/experiment-runs/{run['id']}/logs",
        json={"level": "info", "message": "epoch 1 done"},
        headers=h,
    )
    assert log.status_code == 201
    logs = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/logs")).json()
    assert logs[0]["message"] == "epoch 1 done"

    art = await client.post(
        f"/projects/{p}/experiment-runs/{run['id']}/artifacts",
        json={"name": "model.ckpt", "artifact_type": "checkpoint", "uri": "s3://x"},
        headers=h,
    )
    assert art.status_code == 201
    arts = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/artifacts")).json()
    assert arts[0]["name"] == "model.ckpt"


async def test_analyze_creates_agent_run(client) -> None:
    p = await _project(client, "expa@example.com")
    h = csrf_headers(client)
    exp = (await client.post(f"/projects/{p}/experiments", json={"name": "E"}, headers=h)).json()
    run = (
        await client.post(
            f"/projects/{p}/experiments/{exp['id']}/runs",
            json={"name": "r", "status": "completed"},
            headers=h,
        )
    ).json()
    resp = await client.post(f"/projects/{p}/experiment-runs/{run['id']}/analyze", headers=h)
    assert resp.status_code == 201
    assert resp.json()["status"] == "queued"


async def test_experiment_tenant_isolation(make_client) -> None:
    a = make_client()
    b = make_client()
    p = await _project(a, "exp-a@example.com")
    await register(b, email="exp-b@example.com")
    assert (await b.get(f"/projects/{p}/experiments")).status_code == 404
