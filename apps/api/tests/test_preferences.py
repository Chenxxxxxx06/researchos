"""User preferences: defaults, field-wise merge, full-replace PUT, isolation."""

from __future__ import annotations

# Register the user_preferences table on Base.metadata for conftest's
# create_all even before the M1 aggregator lands.
import researchos.preferences.models  # noqa: F401

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_defaults_when_no_rows(client) -> None:
    await register(client, email="pref-default@example.com")
    resp = await client.get("/users/me/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["global"] is None
    assert body["effective"] == {
        "theme": "system",
        "language": "zh-CN",
        "figure_style_slug": "clean-serif",
        "extra": {},
    }


async def test_global_then_project_merge_fieldwise(client) -> None:
    p = await _project(client, "pref-merge@example.com")
    h = csrf_headers(client)

    put = await client.put("/users/me/preferences", json={"theme": "dark"}, headers=h)
    assert put.status_code == 200
    body = put.json()
    assert body["global"]["theme"] == "dark"
    assert body["global"]["language"] is None
    assert body["effective"]["theme"] == "dark"
    assert body["effective"]["language"] == "zh-CN"  # default fills the gap

    put_p = await client.put(
        f"/projects/{p}/preferences",
        json={"figure_style_slug": "ieee", "extra": {"panel": "wide"}},
        headers=h,
    )
    assert put_p.status_code == 200
    scoped = put_p.json()
    assert scoped["project"]["figure_style_slug"] == "ieee"
    assert scoped["global"]["theme"] == "dark"
    # Field-wise: theme from global, slug from project, language from defaults.
    assert scoped["effective"] == {
        "theme": "dark",
        "language": "zh-CN",
        "figure_style_slug": "ieee",
        "extra": {"panel": "wide"},
    }

    # The global surface stays project-free.
    me = (await client.get("/users/me/preferences")).json()
    assert me["effective"]["figure_style_slug"] == "clean-serif"


async def test_put_is_full_replace(client) -> None:
    await register(client, email="pref-replace@example.com")
    h = csrf_headers(client)

    await client.put(
        "/users/me/preferences",
        json={"theme": "dark", "language": "en", "extra": {"a": 1}},
        headers=h,
    )
    replaced = (
        await client.put("/users/me/preferences", json={"language": "en"}, headers=h)
    ).json()
    # Omitted fields are cleared (NULL = no opinion), not merged.
    assert replaced["global"]["theme"] is None
    assert replaced["global"]["extra"] == {}
    assert replaced["effective"]["theme"] == "system"
    assert replaced["effective"]["language"] == "en"


async def test_validation_rejects_unknown_values(client) -> None:
    await register(client, email="pref-invalid@example.com")
    h = csrf_headers(client)

    assert (
        await client.put("/users/me/preferences", json={"theme": "sepia"}, headers=h)
    ).status_code == 422
    assert (
        await client.put("/users/me/preferences", json={"language": "fr"}, headers=h)
    ).status_code == 422
    assert (
        await client.put(
            "/users/me/preferences", json={"figure_style_slug": "no-such-preset"}, headers=h
        )
    ).status_code == 422
    # extra must stay flat scalars.
    assert (
        await client.put(
            "/users/me/preferences", json={"extra": {"nested": {"x": 1}}}, headers=h
        )
    ).status_code == 422
    # extra capped at 8 KB.
    assert (
        await client.put(
            "/users/me/preferences", json={"extra": {"blob": "x" * 9000}}, headers=h
        )
    ).status_code == 422


async def test_rows_are_personal_per_user(make_client) -> None:
    a = make_client()
    b = make_client()
    p = await _project(a, "pref-a@example.com")
    await a.put("/users/me/preferences", json={"theme": "dark"}, headers=csrf_headers(a))
    await a.put(
        f"/projects/{p}/preferences", json={"figure_style_slug": "ieee"}, headers=csrf_headers(a)
    )

    await register(b, email="pref-b@example.com")
    me_b = (await b.get("/users/me/preferences")).json()
    assert me_b["global"] is None
    assert me_b["effective"]["theme"] == "system"

    # B is not a member of A's project: membership hidden, not 403.
    assert (await b.get(f"/projects/{p}/preferences")).status_code == 404


async def test_project_scope_is_per_member(make_client) -> None:
    a = make_client()
    b = make_client()
    await register(a, email="pref-owner@example.com")
    org_id = (await a.get("/organizations")).json()[0]["id"]
    p = (await a.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(a)
    )).json()["id"]
    await register(b, email="pref-member@example.com")
    # User must belong to the organization before being added to the project.
    await a.post(
        f"/organizations/{org_id}/members",
        json={"email": "pref-member@example.com", "role": "member"},
        headers=csrf_headers(a),
    )
    added = await a.post(
        f"/projects/{p}/members",
        json={"email": "pref-member@example.com", "role": "viewer"},
        headers=csrf_headers(a),
    )
    assert added.status_code == 201

    await a.put(
        f"/projects/{p}/preferences", json={"figure_style_slug": "dark"}, headers=csrf_headers(a)
    )
    # VIEWER manages their own personal row; A's row is invisible to B.
    b_prefs = (await b.get(f"/projects/{p}/preferences")).json()
    assert b_prefs["project"] is None
    assert b_prefs["effective"]["figure_style_slug"] == "clean-serif"

    put_b = await b.put(
        f"/projects/{p}/preferences", json={"figure_style_slug": "nature"}, headers=csrf_headers(b)
    )
    assert put_b.status_code == 200
    assert put_b.json()["effective"]["figure_style_slug"] == "nature"

    a_prefs = (await a.get(f"/projects/{p}/preferences")).json()
    assert a_prefs["effective"]["figure_style_slug"] == "dark"
