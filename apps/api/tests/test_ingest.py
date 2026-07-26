"""NDJSON telemetry ingest: tokens, bearer auth, partial acceptance, status."""

from __future__ import annotations

import json

# Register the new tables on Base.metadata for conftest's create_all even
# before the M1 aggregator lands.
import researchos.figures.models  # noqa: F401

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _experiment_and_run(
    client, project_id: str, status: str = "running"
) -> tuple[dict, dict]:
    h = csrf_headers(client)
    exp = (
        await client.post(
            f"/projects/{project_id}/experiments", json={"name": "E"}, headers=h
        )
    ).json()
    run = (
        await client.post(
            f"/projects/{project_id}/experiments/{exp['id']}/runs",
            json={"name": "r", "status": status},
            headers=h,
        )
    ).json()
    return exp, run


async def _token(client, project_id: str, name: str = "gpu-box-1") -> dict:
    resp = await client.post(
        f"/projects/{project_id}/experiments/ingest-tokens",
        json={"name": name},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    return resp.json()


def _ndjson(lines: list[dict | str]) -> bytes:
    rendered = [line if isinstance(line, str) else json.dumps(line) for line in lines]
    return ("\n".join(rendered) + "\n").encode("utf-8")


async def _ingest(script_client, run_id: str, token: str, lines: list[dict | str]):
    return await script_client.post(
        f"/ingest/experiment-runs/{run_id}",
        content=_ndjson(lines),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-ndjson",
        },
    )


async def test_token_lifecycle_plaintext_once_and_masked_list(client) -> None:
    p = await _project(client, "ingest-token@example.com")
    created = await _token(client, p)
    assert created["token"].startswith("rosit_")
    assert len(created["token"]) == len("rosit_") + 40
    assert created["token_prefix"] == created["token"][:12]

    listed = (await client.get(f"/projects/{p}/experiments/ingest-tokens")).json()
    assert len(listed) == 1
    assert "token" not in listed[0]  # plaintext never re-surfaces
    assert listed[0]["token_prefix"] == created["token_prefix"]
    assert listed[0]["revoked_at"] is None

    revoke = await client.delete(
        f"/projects/{p}/experiments/ingest-tokens/{created['id']}",
        headers=csrf_headers(client),
    )
    assert revoke.status_code == 204
    listed = (await client.get(f"/projects/{p}/experiments/ingest-tokens")).json()
    assert listed[0]["revoked_at"] is not None
    # Idempotent revoke.
    again = await client.delete(
        f"/projects/{p}/experiments/ingest-tokens/{created['id']}",
        headers=csrf_headers(client),
    )
    assert again.status_code == 204


async def test_ingest_metrics_and_logs_without_cookies(client, make_client) -> None:
    p = await _project(client, "ingest-happy@example.com")
    _, run = await _experiment_and_run(client, p)
    token = (await _token(client, p))["token"]

    script = make_client()  # fresh client: no session cookie, no CSRF
    resp = await _ingest(
        script,
        run["id"],
        token,
        [
            {"t": "metric", "name": "loss", "step": 0, "value": 1.0},
            {"t": "metric", "name": "loss", "step": 1, "value": 0.5},
            {"t": "log", "level": "info", "msg": "epoch 0 done"},
            {"t": "log", "level": "info", "msg": "epoch 1 done"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"accepted": 4, "rejected": [], "run_status": "running"}

    metrics = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/metrics")).json()
    assert len(metrics) == 2
    logs = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/logs")).json()
    assert [log["seq"] for log in logs] == [0, 1]

    # A second batch continues the seq block (contiguous, no COUNT(*) races).
    second = await _ingest(
        script, run["id"], token, [{"t": "log", "msg": "epoch 2 done"}]
    )
    assert second.status_code == 200
    logs = (await client.get(f"/projects/{p}/experiment-runs/{run['id']}/logs")).json()
    assert [log["seq"] for log in logs] == [0, 1, 2]


async def test_ingest_partial_acceptance_with_line_numbers(client, make_client) -> None:
    p = await _project(client, "ingest-mixed@example.com")
    _, run = await _experiment_and_run(client, p)
    token = (await _token(client, p))["token"]
    script = make_client()

    resp = await _ingest(
        script,
        run["id"],
        token,
        [
            {"t": "metric", "name": "loss", "step": 0, "value": 1.0},
            "not json at all",
            {"t": "metric", "name": "loss", "step": 1, "value": "NaN-ish"},
            {"t": "artifact", "name": "x"},  # unknown type line
            {"t": "log", "msg": "fine"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 2
    assert [r["line"] for r in body["rejected"]] == [2, 3, 4]
    assert all(r["error"] for r in body["rejected"])


async def test_ingest_auth_failures(client, make_client) -> None:
    p = await _project(client, "ingest-auth@example.com")
    _, run = await _experiment_and_run(client, p)
    created = await _token(client, p)
    script = make_client()

    line = [{"t": "log", "msg": "hi"}]

    missing = await script.post(
        f"/ingest/experiment-runs/{run['id']}", content=_ndjson(line)
    )
    assert missing.status_code == 401

    unknown = await _ingest(script, run["id"], "rosit_" + "0" * 40, line)
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_token"

    await client.delete(
        f"/projects/{p}/experiments/ingest-tokens/{created['id']}",
        headers=csrf_headers(client),
    )
    revoked = await _ingest(script, run["id"], created["token"], line)
    assert revoked.status_code == 401


async def test_ingest_token_scoped_to_project(make_client) -> None:
    a = make_client()
    b = make_client()
    pa = await _project(a, "ingest-scope-a@example.com")
    pb = await _project(b, "ingest-scope-b@example.com")
    _, run_b = await _experiment_and_run(b, pb)
    token_a = (await _token(a, pa))["token"]

    script = make_client()
    resp = await _ingest(script, run_b["id"], token_a, [{"t": "log", "msg": "hi"}])
    assert resp.status_code == 404  # foreign run hidden, not 403


async def test_ingest_status_line_transitions_and_flags_anchor(client, make_client) -> None:
    p = await _project(client, "ingest-status@example.com")
    exp, run1 = await _experiment_and_run(client, p)
    h = csrf_headers(client)

    # Capture an anchor on run-1.
    await client.post(
        f"/projects/{p}/experiment-runs/{run1['id']}/metrics",
        json={"points": [{"name": "acc", "step": 0, "value": 0.5}]},
        headers=h,
    )
    await client.patch(
        f"/projects/{p}/experiment-runs/{run1['id']}", json={"status": "completed"}, headers=h
    )
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "Acc", "experiment_id": exp["id"], "metric_name": "acc"},
        headers=h,
    )
    await client.post(f"/projects/{p}/anchors/refresh", headers=h)

    run2 = (
        await client.post(
            f"/projects/{p}/experiments/{exp['id']}/runs",
            json={"name": "r2", "status": "running"},
            headers=h,
        )
    ).json()
    token = (await _token(client, p))["token"]
    script = make_client()

    resp = await _ingest(
        script,
        run2["id"],
        token,
        [
            {"t": "metric", "name": "acc", "step": 0, "value": 0.9},
            {"t": "status", "status": "running"},  # idempotent no-op accepted
            {"t": "status", "status": "completed"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 3
    assert body["rejected"] == []
    assert body["run_status"] == "completed"

    run_after = (await client.get(f"/projects/{p}/experiment-runs/{run2['id']}")).json()
    assert run_after["status"] == "completed"
    assert run_after["finished_at"] is not None

    anchors = (await client.get(f"/projects/{p}/anchors")).json()
    assert anchors[0]["stale"] is True  # completion hook fired from ingest

    # Further transitions on the terminal run reject the line, not the request.
    late = await _ingest(script, run2["id"], token, [{"t": "status", "status": "running"}])
    assert late.status_code == 200
    late_body = late.json()
    assert late_body["accepted"] == 0
    assert [r["line"] for r in late_body["rejected"]] == [1]
    assert late_body["run_status"] == "completed"


async def test_ingest_payload_caps(client, make_client) -> None:
    p = await _project(client, "ingest-caps@example.com")
    _, run = await _experiment_and_run(client, p)
    token = (await _token(client, p))["token"]
    script = make_client()

    lines: list[dict | str] = [
        {"t": "metric", "name": "loss", "step": i, "value": 0.1} for i in range(1001)
    ]
    resp = await _ingest(script, run["id"], token, lines)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"

    big = await script.post(
        f"/ingest/experiment-runs/{run['id']}",
        content=b"x" * 1_000_001,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert big.status_code == 413
