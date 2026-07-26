"""Figure pipeline: spec validation, sync render, assets, staleness, presets."""

from __future__ import annotations

import uuid

from sqlalchemy import select

# Register the figures tables on Base.metadata for conftest's create_all even
# before the M1 aggregator lands.
from researchos.experiments.models import ExperimentArtifact
from researchos.figures.enums import FigureRenderStatus
from researchos.figures.models import Figure

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _experiment_with_run(client, project_id: str) -> tuple[dict, dict]:
    h = csrf_headers(client)
    exp = (
        await client.post(
            f"/projects/{project_id}/experiments", json={"name": "E"}, headers=h
        )
    ).json()
    run = (
        await client.post(
            f"/projects/{project_id}/experiments/{exp['id']}/runs",
            json={"name": "run-1", "status": "running"},
            headers=h,
        )
    ).json()
    await client.post(
        f"/projects/{project_id}/experiment-runs/{run['id']}/metrics",
        json={
            "points": [
                {"name": "val_acc", "step": s, "value": 0.1 * s} for s in range(5)
            ]
        },
        headers=h,
    )
    run = (
        await client.patch(
            f"/projects/{project_id}/experiment-runs/{run['id']}",
            json={"status": "completed"},
            headers=h,
        )
    ).json()
    return exp, run


def _line_spec(run_id: str) -> dict:
    return {
        "chart": "line",
        "series": [
            {
                "source": {"kind": "run_metric", "run_id": run_id, "metric_name": "val_acc"},
                "label": "baseline",
            }
        ],
        "title": "Validation accuracy",
        "x_label": "step",
        "y_label": "acc",
    }


async def test_create_rejects_cross_project_and_caps(make_client) -> None:
    a = make_client()
    p1 = await _project(a, "fig-a@example.com")
    _, run1 = await _experiment_with_run(a, p1)

    org_id = (await a.get("/organizations")).json()[0]["id"]
    p2 = (
        await a.post(
            "/projects", json={"organization_id": org_id, "name": "P2"}, headers=csrf_headers(a)
        )
    ).json()["id"]

    foreign = await a.post(
        f"/projects/{p2}/figures",
        json={"name": "leak", "spec": _line_spec(run1["id"])},
        headers=csrf_headers(a),
    )
    assert foreign.status_code == 404

    too_many_series = {
        "chart": "line",
        "series": [
            {"source": {"kind": "inline", "points": [[0, 1]]}} for _ in range(9)
        ],
    }
    capped = await a.post(
        f"/projects/{p1}/figures",
        json={"name": "capped", "spec": too_many_series},
        headers=csrf_headers(a),
    )
    assert capped.status_code == 422

    dup_spec = {
        "chart": "line",
        "series": [{"source": {"kind": "inline", "points": [[0, 1], [1, 2]]}}],
    }
    h = csrf_headers(a)
    first = await a.post(
        f"/projects/{p1}/figures", json={"name": "dup", "spec": dup_spec}, headers=h
    )
    assert first.status_code == 201
    assert first.json()["status"] == "pending"
    second = await a.post(
        f"/projects/{p1}/figures", json={"name": "dup", "spec": dup_spec}, headers=h
    )
    assert second.status_code == 409


async def test_sync_render_persists_assets_and_links_artifact(client, db_session) -> None:
    p = await _project(client, "fig-render@example.com")
    _, run = await _experiment_with_run(client, p)
    h = csrf_headers(client)

    figure = (
        await client.post(
            f"/projects/{p}/figures",
            json={"name": "lr-ablation", "spec": _line_spec(run["id"])},
            headers=h,
        )
    ).json()

    rendered = await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )
    assert rendered.status_code == 200
    body = rendered.json()
    assert body["status"] == "rendered"
    formats = {a["format"] for a in body["assets"]}
    assert formats == {"svg", "png"}
    assert all(a["size_bytes"] > 0 and len(a["sha256"]) == 64 for a in body["assets"])

    detail = (await client.get(f"/projects/{p}/figures/{figure['id']}")).json()
    assert detail["status"] == "rendered"
    assert detail["rendered_style_slug"] == "clean-serif"  # default preference
    assert detail["rendered_style_version"] == "1.0.0"
    assert detail["style_outdated"] is False
    assert detail["source_run_ids"] == [run["id"]]
    assert detail["last_rendered_at"] is not None
    assert detail["stale"] is False

    # Run-artifact link with figure provenance in metadata_json.
    artifacts = (
        await client.get(f"/projects/{p}/experiment-runs/{run['id']}/artifacts")
    ).json()
    fig_artifacts = [a for a in artifacts if a["artifact_type"] == "figure"]
    assert len(fig_artifacts) == 1
    assert fig_artifacts[0]["name"] == "lr-ablation.svg"
    assert fig_artifacts[0]["uri"] == f"/projects/{p}/figures/{figure['id']}/assets/svg"
    row = await db_session.scalar(
        select(ExperimentArtifact).where(ExperimentArtifact.id == uuid.UUID(fig_artifacts[0]["id"]))
    )
    assert row is not None and row.metadata_json["figure_id"] == figure["id"]

    # Re-render upserts assets and the artifact link (no growth).
    again = await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )
    assert again.status_code == 200
    artifacts = (
        await client.get(f"/projects/{p}/experiment-runs/{run['id']}/artifacts")
    ).json()
    assert len([a for a in artifacts if a["artifact_type"] == "figure"]) == 1


async def test_asset_get_content_type_and_etag(client) -> None:
    p = await _project(client, "fig-etag@example.com")
    _, run = await _experiment_with_run(client, p)
    h = csrf_headers(client)
    figure = (
        await client.post(
            f"/projects/{p}/figures",
            json={"name": "etag", "spec": _line_spec(run["id"])},
            headers=h,
        )
    ).json()

    missing = await client.get(f"/projects/{p}/figures/{figure['id']}/assets/svg")
    assert missing.status_code == 404  # never rendered

    await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )

    svg = await client.get(f"/projects/{p}/figures/{figure['id']}/assets/svg")
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.content.startswith(b"<?xml")
    etag = svg.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')

    png = await client.get(f"/projects/{p}/figures/{figure['id']}/assets/png")
    assert png.headers["content-type"] == "image/png"
    assert png.content.startswith(b"\x89PNG")

    not_modified = await client.get(
        f"/projects/{p}/figures/{figure['id']}/assets/svg",
        headers={"If-None-Match": etag},
    )
    assert not_modified.status_code == 304


async def test_sync_caps_and_rendering_conflict(client, db_session) -> None:
    p = await _project(client, "fig-caps@example.com")
    h = csrf_headers(client)

    five_series = {
        "chart": "line",
        "series": [
            {"source": {"kind": "inline", "points": [[0, 1], [1, 2]]}} for _ in range(5)
        ],
    }
    figure = (
        await client.post(
            f"/projects/{p}/figures", json={"name": "big", "spec": five_series}, headers=h
        )
    ).json()
    too_large = await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )
    assert too_large.status_code == 422
    assert too_large.json()["error"]["code"] == "figure_too_large_for_sync"

    many_points = {
        "chart": "line",
        "series": [
            {
                "source": {
                    "kind": "inline",
                    "points": [[i, i * 0.5] for i in range(1500)],
                }
            }
            for _ in range(2)
        ],
    }
    dense = (
        await client.post(
            f"/projects/{p}/figures", json={"name": "dense", "spec": many_points}, headers=h
        )
    ).json()
    too_dense = await client.post(
        f"/projects/{p}/figures/{dense['id']}/render", json={"mode": "sync"}, headers=h
    )
    assert too_dense.status_code == 422
    assert too_dense.json()["error"]["code"] == "figure_too_large_for_sync"

    # A figure mid-render rejects a second async render request.
    row = await db_session.get(Figure, uuid.UUID(dense["id"]))
    row.status = FigureRenderStatus.RENDERING
    await db_session.commit()
    busy = await client.post(
        f"/projects/{p}/figures/{dense['id']}/render", json={"mode": "async"}, headers=h
    )
    assert busy.status_code == 409


async def test_run_completion_flips_latest_source_figure_stale(client) -> None:
    p = await _project(client, "fig-stale@example.com")
    exp, _run = await _experiment_with_run(client, p)
    h = csrf_headers(client)

    latest_spec = {
        "chart": "line",
        "series": [
            {
                "source": {
                    "kind": "run_metric",
                    "experiment_id": exp["id"],
                    "metric_name": "val_acc",
                },
                "label": "latest",
            }
        ],
    }
    figure = (
        await client.post(
            f"/projects/{p}/figures", json={"name": "latest", "spec": latest_spec}, headers=h
        )
    ).json()
    await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )
    assert (await client.get(f"/projects/{p}/figures/{figure['id']}")).json()["stale"] is False

    run2 = (
        await client.post(
            f"/projects/{p}/experiments/{exp['id']}/runs",
            json={"name": "run-2", "status": "running"},
            headers=h,
        )
    ).json()
    await client.patch(
        f"/projects/{p}/experiment-runs/{run2['id']}",
        json={"status": "completed"},
        headers=h,
    )
    assert (await client.get(f"/projects/{p}/figures/{figure['id']}")).json()["stale"] is True

    # Updating the spec resets render state.
    updated = (
        await client.patch(
            f"/projects/{p}/figures/{figure['id']}", json={"spec": latest_spec}, headers=h
        )
    ).json()
    assert updated["status"] == "pending"
    assert updated["stale"] is False


async def test_style_presets_endpoint(client) -> None:
    p = await _project(client, "fig-presets@example.com")
    resp = await client.get(f"/projects/{p}/figures/style-presets")
    assert resp.status_code == 200
    presets = resp.json()
    slugs = {item["slug"] for item in presets}
    assert slugs == {"clean-serif", "ieee", "nature", "dark", "minimal-gray"}
    for item in presets:
        assert item["version"]
        assert item["palette"]
        # CONSOLIDATION §5: the style object drives frontend SVG thumbnails.
        style = item["style"]
        assert style["palette"] == item["palette"]
        assert style["font_family"] in ("serif", "sans")
        assert isinstance(style["grid"], bool)
        assert isinstance(style["legend_frame"], bool)


async def test_figure_style_follows_user_preference(client) -> None:
    p = await _project(client, "fig-pref@example.com")
    _, run = await _experiment_with_run(client, p)
    h = csrf_headers(client)

    await client.put(
        "/users/me/preferences",
        json={"figure_style_slug": "ieee"},
        headers=h,
    )
    figure = (
        await client.post(
            f"/projects/{p}/figures",
            json={"name": "styled", "spec": _line_spec(run["id"])},
            headers=h,
        )
    ).json()
    await client.post(
        f"/projects/{p}/figures/{figure['id']}/render", json={"mode": "sync"}, headers=h
    )
    detail = (await client.get(f"/projects/{p}/figures/{figure['id']}")).json()
    assert detail["rendered_style_slug"] == "ieee"
