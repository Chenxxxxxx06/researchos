"""Experiments hardening: IDOR fix, run transitions, atomic log seqs, metric_meta."""

from __future__ import annotations

import asyncio

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _experiment(client, project_id: str, name: str = "E") -> dict:
    resp = await client.post(
        f"/projects/{project_id}/experiments", json={"name": name}, headers=csrf_headers(client)
    )
    return resp.json()


async def _run(client, project_id: str, experiment_id: str, status: str = "running") -> dict:
    resp = await client.post(
        f"/projects/{project_id}/experiments/{experiment_id}/runs",
        json={"name": "r", "status": status},
        headers=csrf_headers(client),
    )
    return resp.json()


async def test_list_runs_idor_cross_project_is_404(make_client) -> None:
    a = make_client()
    b = make_client()
    p1 = await _project(a, "hard-a@example.com")
    exp = await _experiment(a, p1)
    await _run(a, p1, exp["id"])

    # B is a member of their own project only; supplying it in the path must
    # not expose another project's experiment runs.
    p2 = await _project(b, "hard-b@example.com")
    resp = await b.get(f"/projects/{p2}/experiments/{exp['id']}/runs")
    assert resp.status_code == 404

    # The legitimate owner still lists runs.
    ok = await a.get(f"/projects/{p1}/experiments/{exp['id']}/runs")
    assert ok.status_code == 200
    assert len(ok.json()) == 1


async def test_terminal_run_rejects_further_transitions(client) -> None:
    p = await _project(client, "hard-terminal@example.com")
    exp = await _experiment(client, p)
    run = await _run(client, p, exp["id"], status="completed")

    resp = await client.patch(
        f"/projects/{p}/experiment-runs/{run['id']}",
        json={"status": "running"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_transition"


async def test_transitions_stamp_started_and_finished(client) -> None:
    p = await _project(client, "hard-stamps@example.com")
    exp = await _experiment(client, p)
    run = await _run(client, p, exp["id"], status="queued")
    assert run["started_at"] is None
    assert run["finished_at"] is None

    h = csrf_headers(client)
    running = (
        await client.patch(
            f"/projects/{p}/experiment-runs/{run['id']}", json={"status": "running"}, headers=h
        )
    ).json()
    assert running["started_at"] is not None
    assert running["finished_at"] is None

    # Idempotent same-status PATCH is a 200 no-op.
    again = await client.patch(
        f"/projects/{p}/experiment-runs/{run['id']}", json={"status": "running"}, headers=h
    )
    assert again.status_code == 200
    assert again.json()["started_at"] == running["started_at"]

    cancelled = (
        await client.patch(
            f"/projects/{p}/experiment-runs/{run['id']}", json={"status": "cancelled"}, headers=h
        )
    ).json()
    assert cancelled["finished_at"] is not None


async def test_run_created_terminal_gets_finished_at(client) -> None:
    p = await _project(client, "hard-born-done@example.com")
    exp = await _experiment(client, p)
    run = await _run(client, p, exp["id"], status="cancelled")
    assert run["finished_at"] is not None


async def test_concurrent_log_appends_get_unique_seqs(client) -> None:
    p = await _project(client, "hard-logs@example.com")
    exp = await _experiment(client, p)
    run = await _run(client, p, exp["id"])
    h = csrf_headers(client)

    async def _append(i: int):
        return await client.post(
            f"/projects/{p}/experiment-runs/{run['id']}/logs",
            json={"level": "info", "message": f"line {i}"},
            headers=h,
        )

    responses = await asyncio.gather(*[_append(i) for i in range(20)])
    assert all(r.status_code == 201 for r in responses)
    seqs = sorted(r.json()["seq"] for r in responses)
    assert seqs == list(range(20))

    logs = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/logs")).json()
    assert [log["seq"] for log in logs] == list(range(20))


async def test_patch_experiment_metric_meta(client) -> None:
    p = await _project(client, "hard-meta@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    resp = await client.patch(
        f"/projects/{p}/experiments/{exp['id']}",
        json={"metric_meta": {"val_acc": {"direction": "max", "unit": "%"}}},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["metric_meta"]["val_acc"]["direction"] == "max"

    # Persisted on subsequent reads.
    got = (await client.get(f"/projects/{p}/experiments/{exp['id']}")).json()
    assert got["metric_meta"]["val_acc"] == {"direction": "max", "unit": "%"}

    bad = await client.patch(
        f"/projects/{p}/experiments/{exp['id']}",
        json={"metric_meta": {"val_acc": {"direction": "sideways"}}},
        headers=h,
    )
    assert bad.status_code == 422

    missing = await client.patch(
        f"/projects/{p}/experiments/{'0' * 8 + '-0000-0000-0000-' + '0' * 12}",
        json={"name": "x"},
        headers=h,
    )
    assert missing.status_code == 404
