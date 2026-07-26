"""Named result anchors: CRUD, resolution, formatting, macros.tex, staleness."""

from __future__ import annotations

import pytest

# Register the figures tables on Base.metadata for conftest's create_all even
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


async def _experiment(client, project_id: str, name: str = "lr-sweep") -> dict:
    resp = await client.post(
        f"/projects/{project_id}/experiments", json={"name": name}, headers=csrf_headers(client)
    )
    return resp.json()


async def _completed_run(
    client, project_id: str, experiment_id: str, *, name: str, points: list[dict]
) -> dict:
    h = csrf_headers(client)
    run = (
        await client.post(
            f"/projects/{project_id}/experiments/{experiment_id}/runs",
            json={"name": name, "status": "running"},
            headers=h,
        )
    ).json()
    if points:
        await client.post(
            f"/projects/{project_id}/experiment-runs/{run['id']}/metrics",
            json={"points": points},
            headers=h,
        )
    resp = await client.patch(
        f"/projects/{project_id}/experiment-runs/{run['id']}",
        json={"status": "completed"},
        headers=h,
    )
    return resp.json()


async def test_anchor_crud_and_validation(client) -> None:
    p = await _project(client, "anchor-crud@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    created = await client.post(
        f"/projects/{p}/anchors",
        json={"name": "BestAcc", "experiment_id": exp["id"], "metric_name": "val_acc",
              "aggregation": "best", "decimals": 2, "scale": 100.0, "suffix": "\\%"},
        headers=h,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["macro"] == "\\ROSBestAcc"
    assert body["captured_value"] is None
    assert body["stale"] is False

    dup = await client.post(
        f"/projects/{p}/anchors",
        json={"name": "BestAcc", "experiment_id": exp["id"], "metric_name": "val_acc"},
        headers=h,
    )
    assert dup.status_code == 409

    # LaTeX control words are letters-only.
    for bad_name in ("Best_Acc", "Best1", "", "a" * 49):
        bad = await client.post(
            f"/projects/{p}/anchors",
            json={"name": bad_name, "experiment_id": exp["id"], "metric_name": "val_acc"},
            headers=h,
        )
        assert bad.status_code == 422, bad_name

    bad_decimals = await client.post(
        f"/projects/{p}/anchors",
        json={"name": "TooDeep", "experiment_id": exp["id"], "metric_name": "x", "decimals": 11},
        headers=h,
    )
    assert bad_decimals.status_code == 422

    listed = (await client.get(f"/projects/{p}/anchors")).json()
    assert [a["name"] for a in listed] == ["BestAcc"]

    got = await client.get(f"/projects/{p}/anchors/{body['id']}")
    assert got.status_code == 200

    deleted = await client.delete(f"/projects/{p}/anchors/{body['id']}", headers=h)
    assert deleted.status_code == 204
    assert (await client.get(f"/projects/{p}/anchors/{body['id']}")).status_code == 404


async def test_anchor_source_must_be_in_project(make_client) -> None:
    a = make_client()
    p1 = await _project(a, "anchor-idor@example.com")
    exp1 = await _experiment(a, p1)

    org_id = (await a.get("/organizations")).json()[0]["id"]
    p2 = (
        await a.post(
            "/projects", json={"organization_id": org_id, "name": "P2"}, headers=csrf_headers(a)
        )
    ).json()["id"]

    resp = await a.post(
        f"/projects/{p2}/anchors",
        json={"name": "Foreign", "experiment_id": exp1["id"], "metric_name": "x"},
        headers=csrf_headers(a),
    )
    assert resp.status_code == 404


async def test_resolution_pinned_vs_latest_and_direction(client) -> None:
    p = await _project(client, "anchor-resolve@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    run1 = await _completed_run(
        client, p, exp["id"], name="run-1",
        points=[{"name": "val_acc", "step": 0, "value": 0.5},
                {"name": "score", "step": 0, "value": 3.0},
                {"name": "score", "step": 1, "value": 1.0},
                {"name": "score", "step": 2, "value": 2.0}],
    )
    run2 = await _completed_run(
        client, p, exp["id"], name="run-2",
        points=[{"name": "val_acc", "step": 0, "value": 0.7}],
    )

    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "Pinned", "experiment_id": exp["id"], "run_id": run1["id"],
              "metric_name": "val_acc", "aggregation": "final", "decimals": 2},
        headers=h,
    )
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "Latest", "experiment_id": exp["id"],
              "metric_name": "val_acc", "aggregation": "final", "decimals": 2,
              "scale": 100.0, "suffix": "\\%"},
        headers=h,
    )
    # "score" has no min-hint; explicit metadata must flip best to min.
    await client.patch(
        f"/projects/{p}/experiments/{exp['id']}",
        json={"metric_meta": {"score": {"direction": "min"}}},
        headers=h,
    )
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "BestScore", "experiment_id": exp["id"], "run_id": run1["id"],
              "metric_name": "score", "aggregation": "best", "decimals": 1},
        headers=h,
    )

    refreshed = (await client.post(f"/projects/{p}/anchors/refresh", headers=h)).json()
    assert refreshed["refreshed"] == 3
    assert refreshed["unresolved"] == 0
    by_name = {item["name"]: item for item in refreshed["anchors"]}
    assert by_name["Pinned"]["value"] == pytest.approx(0.5)
    assert by_name["Pinned"]["run_id"] == run1["id"]
    assert by_name["Latest"]["value"] == pytest.approx(0.7)
    assert by_name["Latest"]["run_id"] == run2["id"]
    assert by_name["Latest"]["formatted"] == "70.00\\%"
    assert by_name["BestScore"]["value"] == pytest.approx(1.0)
    assert by_name["BestScore"]["formatted"] == "1.0"


async def test_macros_tex_golden_and_unresolved(client) -> None:
    p = await _project(client, "anchor-macros@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    run1 = await _completed_run(
        client, p, exp["id"], name="run-47",
        points=[{"name": "val_acc", "step": 3, "value": 0.9421}],
    )
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "BestAcc", "experiment_id": exp["id"], "run_id": run1["id"],
              "metric_name": "val_acc", "aggregation": "best",
              "decimals": 2, "scale": 100.0, "suffix": "\\%"},
        headers=h,
    )
    # No train_loss data anywhere -> unresolved, but the file still compiles.
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "FinalLoss", "experiment_id": exp["id"],
              "metric_name": "train_loss", "aggregation": "final"},
        headers=h,
    )

    resp = await client.get(f"/projects/{p}/anchors/macros.tex")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-tex")
    lines = resp.text.splitlines()
    assert lines[0] == (
        "% Auto-generated by ResearchOS. Do not edit. "
        f"Regenerate: GET /projects/{p}/anchors/macros.tex"
    )
    assert lines[1].startswith("% generated_at=") and f"project={p}" in lines[1]
    # Deterministic ordering by name: BestAcc before FinalLoss.
    expected_comment = (
        '% \\ROSBestAcc <- experiment "lr-sweep" run "run-47" metric val_acc agg=best'
    )
    assert lines[2] == expected_comment
    assert lines[3] == "\\newcommand{\\ROSBestAcc}{94.21\\%}"
    assert lines[4] == (
        "% \\ROSFinalLoss <- experiment \"lr-sweep\" run latest metric train_loss "
        "agg=final [UNRESOLVED]"
    )
    assert lines[5] == "\\newcommand{\\ROSFinalLoss}{\\textbf{??}}"

    # refresh=true (default) captured snapshots as a side effect.
    anchors = (await client.get(f"/projects/{p}/anchors")).json()
    best = next(a for a in anchors if a["name"] == "BestAcc")
    assert best["captured_value"] == pytest.approx(0.9421)

    # refresh=false renders from stored snapshots only (identical values here).
    stored = await client.get(f"/projects/{p}/anchors/macros.tex", params={"refresh": "false"})
    assert "\\newcommand{\\ROSBestAcc}{94.21\\%}" in stored.text


async def test_staleness_hook_report_and_refresh(client) -> None:
    p = await _project(client, "anchor-stale@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    await _completed_run(
        client, p, exp["id"], name="run-1",
        points=[{"name": "acc", "step": 0, "value": 0.5}],
    )
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "Acc", "experiment_id": exp["id"], "metric_name": "acc",
              "aggregation": "final", "decimals": 2},
        headers=h,
    )
    await client.post(f"/projects/{p}/anchors/refresh", headers=h)

    # A never-captured anchor must NOT be flagged by the hook.
    await client.post(
        f"/projects/{p}/anchors",
        json={"name": "Uncaptured", "experiment_id": exp["id"], "metric_name": "acc"},
        headers=h,
    )

    run2 = await _completed_run(
        client, p, exp["id"], name="run-2",
        points=[{"name": "acc", "step": 0, "value": 0.9}],
    )

    anchors = {a["name"]: a for a in (await client.get(f"/projects/{p}/anchors")).json()}
    assert anchors["Acc"]["stale"] is True
    assert anchors["Uncaptured"]["stale"] is False

    report = (await client.get(f"/projects/{p}/anchors/staleness")).json()
    assert report["stale_count"] == 1
    item = next(i for i in report["items"] if i["name"] == "Acc")
    assert item["stale"] is True
    assert item["latest_run_id"] == run2["id"]
    assert item["latest_value"] == pytest.approx(0.9)
    assert item["delta"] == pytest.approx(0.4)
    assert item["delta_pct"] == pytest.approx(80.0)

    refreshed = (await client.post(f"/projects/{p}/anchors/refresh", headers=h)).json()
    assert refreshed["unresolved"] == 0
    anchors = {a["name"]: a for a in (await client.get(f"/projects/{p}/anchors")).json()}
    assert anchors["Acc"]["stale"] is False
    assert anchors["Acc"]["captured_run_id"] == run2["id"]
    assert anchors["Acc"]["captured_value"] == pytest.approx(0.9)


async def test_update_source_resets_capture(client) -> None:
    p = await _project(client, "anchor-update@example.com")
    exp = await _experiment(client, p)
    h = csrf_headers(client)

    await _completed_run(
        client, p, exp["id"], name="run-1",
        points=[{"name": "acc", "step": 0, "value": 0.5}],
    )
    anchor = (
        await client.post(
            f"/projects/{p}/anchors",
            json={"name": "Acc", "experiment_id": exp["id"], "metric_name": "acc"},
            headers=h,
        )
    ).json()
    await client.post(f"/projects/{p}/anchors/refresh", headers=h)

    updated = (
        await client.patch(
            f"/projects/{p}/anchors/{anchor['id']}",
            json={"metric_name": "other"},
            headers=h,
        )
    ).json()
    assert updated["metric_name"] == "other"
    assert updated["captured_value"] is None
    assert updated["captured_run_id"] is None
    assert updated["stale"] is False

    # Display-only changes keep the capture.
    await client.patch(
        f"/projects/{p}/anchors/{anchor['id']}", json={"metric_name": "acc"}, headers=h
    )
    await client.post(f"/projects/{p}/anchors/refresh", headers=h)
    kept = (
        await client.patch(
            f"/projects/{p}/anchors/{anchor['id']}", json={"decimals": 4}, headers=h
        )
    ).json()
    assert kept["captured_value"] is not None
