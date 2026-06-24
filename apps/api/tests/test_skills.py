"""Skills marketplace and skill-builder API tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.skills.seed import seed_first_party

from .helpers import csrf_headers, register


async def _project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_first_party_catalog_and_install(client, db_session: AsyncSession) -> None:
    # The lifespan seeder does not run under the test transport; seed directly.
    await seed_first_party(db_session)
    p = await _project(client, "skill@example.com")
    h = csrf_headers(client)

    catalog = (await client.get(f"/projects/{p}/skills/catalog")).json()
    slugs = {s["slug"] for s in catalog}
    assert {"nature-writing", "cvpr-reviewer", "vlm-evaluation"} <= slugs

    install = await client.post(f"/projects/{p}/skills/cvpr-reviewer/install", headers=h)
    assert install.status_code == 204

    installed = (await client.get(f"/projects/{p}/skills/installed")).json()
    assert any(s["slug"] == "cvpr-reviewer" and s["enabled"] for s in installed)

    # Disable then verify.
    await client.post(
        f"/projects/{p}/skills/cvpr-reviewer/toggle", json={"enabled": False}, headers=h
    )
    detail = (await client.get(f"/projects/{p}/skills/cvpr-reviewer")).json()
    assert detail["installed"] is True
    assert detail["enabled"] is False


async def test_validate_and_create_custom_skill(client) -> None:
    p = await _project(client, "skillb@example.com")
    h = csrf_headers(client)

    # DTO-valid but semantically invalid (no modules, empty prompt template).
    invalid = await client.post(
        f"/projects/{p}/skills/validate",
        json={"slug": "ab", "name": "X", "modules": [], "prompt_template": ""},
        headers=h,
    )
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert invalid.json()["errors"]

    valid_body = {
        "slug": "my-nature-skill",
        "name": "My Nature Skill",
        "version": "1.0.0",
        "description": "Custom writing skill",
        "category": "writing",
        "modules": ["paper"],
        "prompt_template": "Rewrite in Nature style.",
        "workflow": ["analyze", "rewrite"],
        "tool_permissions": [],
        "config_schema": {},
    }
    created = await client.post(f"/projects/{p}/skills/custom", json=valid_body, headers=h)
    assert created.status_code == 201
    assert created.json()["visibility"] == "custom"

    catalog = (await client.get(f"/projects/{p}/skills/catalog")).json()
    assert any(s["slug"] == "my-nature-skill" for s in catalog)


async def test_custom_skill_rejects_unknown_tool(client) -> None:
    p = await _project(client, "skillc@example.com")
    h = csrf_headers(client)
    resp = await client.post(
        f"/projects/{p}/skills/custom",
        json={
            "slug": "bad-skill",
            "name": "Bad",
            "version": "1.0.0",
            "modules": ["research"],
            "prompt_template": "x",
            "tool_permissions": ["os.system"],
        },
        headers=h,
    )
    assert resp.status_code == 422
