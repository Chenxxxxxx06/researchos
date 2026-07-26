"""Freshness feed tests: category derivation (80% rule), cursor round-trip,
Redis cache hits, in-library markers, and offline degradation.

No network: the arXiv fetch is monkeypatched with a recorded fixture; the
cache uses the test Redis (db 15, flushed per test).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ValidationError
from researchos.identity.models import User
from researchos.research.feed import decode_cursor, encode_cursor
from researchos.research.models import Paper
from researchos.research.providers import arxiv as arxiv_module
from researchos.research.providers.base import ProviderError

from .helpers import csrf_headers, register

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XML = (FIXTURES / "arxiv_sample.xml").read_text(encoding="utf-8")


@pytest.fixture
def arxiv_feed(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Serve the recorded feed for every arXiv fetch; capture request params."""

    calls: list[dict] = []

    async def fake_fetch(self, params):  # noqa: ANN001 - test stub
        calls.append(dict(params))
        return SAMPLE_XML

    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", fake_fetch)
    return calls


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _insert_papers(
    db: AsyncSession, project_id: str, email: str, categories: list[str | None]
) -> None:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    for i, category in enumerate(categories):
        db.add(
            Paper(
                project_id=uuid.UUID(project_id),
                source="arxiv",
                external_id=f"2400.1000{i}",
                title=f"Paper {i}",
                authors_json=[],
                url=f"http://arxiv.org/abs/2400.1000{i}",
                primary_category=category,
                imported_by=user.id,
            )
        )
    await db.commit()


# --- cursor codec ------------------------------------------------------------
def test_cursor_round_trip() -> None:
    for offset in (0, 20, 999):
        assert decode_cursor(encode_cursor(offset)) == offset


def test_cursor_rejects_garbage() -> None:
    for bad in ("not-base64!", "eyJ4IjoxfQ", encode_cursor(0)[:-2] + "zz"):
        with pytest.raises(ValidationError):
            decode_cursor(bad)


async def test_invalid_cursor_is_422(client, arxiv_feed) -> None:
    project_id = await _make_project(client, "feed-badcursor@example.com")
    resp = await client.get(f"/projects/{project_id}/papers/feed?cursor=garbage!!")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --- category derivation -----------------------------------------------------
async def test_categories_derived_by_80_percent_rule(client, db_session) -> None:
    project_id = await _make_project(client, "feed-derive@example.com")
    # 5x cs.LG (50%), 3x cs.CL (80% cumulative) -> stat.ML and math.OC excluded.
    await _insert_papers(
        db_session,
        project_id,
        "feed-derive@example.com",
        ["cs.LG"] * 5 + ["cs.CL"] * 3 + ["stat.ML", "math.OC"],
    )
    resp = await client.get(f"/projects/{project_id}/papers/feed/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"categories": ["cs.LG", "cs.CL"], "derived": True}


async def test_categories_empty_library(client) -> None:
    project_id = await _make_project(client, "feed-empty@example.com")
    resp = await client.get(f"/projects/{project_id}/papers/feed/categories")
    assert resp.json() == {"categories": [], "derived": True}


async def test_put_categories_override(client, db_session, arxiv_feed) -> None:
    project_id = await _make_project(client, "feed-prefs@example.com")
    await _insert_papers(
        db_session, project_id, "feed-prefs@example.com", ["cs.LG"] * 5
    )
    resp = await client.put(
        f"/projects/{project_id}/papers/feed/categories",
        json={"categories": ["stat.ML", "cs.CL"]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json() == {"categories": ["stat.ML", "cs.CL"], "derived": False}

    # The feed queries the explicit categories, not the derived ones.
    feed = (await client.get(f"/projects/{project_id}/papers/feed?limit=5")).json()
    assert feed["categories_used"] == ["stat.ML", "cs.CL"]
    assert "cat:stat.ML" in arxiv_feed[0]["search_query"]
    assert "cat:cs.LG" not in arxiv_feed[0]["search_query"]


async def test_put_categories_rejects_bad_slug(client) -> None:
    project_id = await _make_project(client, "feed-badcat@example.com")
    resp = await client.put(
        f"/projects/{project_id}/papers/feed/categories",
        json={"categories": ["cs.LG)"]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 422


# --- feed page, markers, cursor, cache ---------------------------------------
async def test_feed_empty_without_categories(client, arxiv_feed) -> None:
    project_id = await _make_project(client, "feed-none@example.com")
    resp = await client.get(f"/projects/{project_id}/papers/feed")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "next_cursor": None, "categories_used": [], "cached": False}
    assert arxiv_feed == []  # no provider call without categories


async def test_feed_page_markers_cursor_and_cache(client, db_session, arxiv_feed) -> None:
    project_id = await _make_project(client, "feed-page@example.com")
    await _insert_papers(db_session, project_id, "feed-page@example.com", ["cs.LG"] * 3)
    # One fixture entry is already in the library -> in_library marker.
    user = (
        await db_session.execute(
            select(User).where(User.email == "feed-page@example.com")
        )
    ).scalar_one()
    db_session.add(
        Paper(
            project_id=uuid.UUID(project_id),
            source="arxiv",
            external_id="2401.01234",
            title="Already imported",
            authors_json=[],
            url="http://arxiv.org/abs/2401.01234",
            primary_category="cs.LG",
            imported_by=user.id,
        )
    )
    await db_session.commit()

    resp = await client.get(f"/projects/{project_id}/papers/feed?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is False
    assert body["categories_used"] == ["cs.LG"]
    assert [i["external_id"] for i in body["items"]] == ["2401.01234", "2312.05678"]
    assert [i["in_library"] for i in body["items"]] == [True, False]
    # Full page -> opaque cursor for the next offset.
    assert body["next_cursor"] is not None
    assert decode_cursor(body["next_cursor"]) == 2
    params = arxiv_feed[0]
    assert params["start"] == "0"
    assert params["sortBy"] == "submittedDate"
    assert "cat:cs.LG" in params["search_query"]

    # Second call within TTL: served from cache, no new provider call.
    again = (await client.get(f"/projects/{project_id}/papers/feed?limit=2")).json()
    assert again["cached"] is True
    assert [i["external_id"] for i in again["items"]] == ["2401.01234", "2312.05678"]
    assert len(arxiv_feed) == 1

    # Following the cursor is a distinct page (cache miss -> provider call).
    cursor = body["next_cursor"]
    page2 = (
        await client.get(f"/projects/{project_id}/papers/feed?cursor={cursor}&limit=2")
    ).json()
    assert len(arxiv_feed) == 2
    assert arxiv_feed[1]["start"] == "2"
    assert page2["next_cursor"] is not None  # fixture still fills the page

    # A short page (limit above fixture size) ends pagination.
    short = (await client.get(f"/projects/{project_id}/papers/feed?limit=5")).json()
    assert short["next_cursor"] is None


async def test_feed_offline_serves_cached_page_else_502(
    client, db_session, arxiv_feed, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "feed-offline@example.com")
    await _insert_papers(db_session, project_id, "feed-offline@example.com", ["cs.LG"] * 3)

    warm = (await client.get(f"/projects/{project_id}/papers/feed?limit=2")).json()
    assert warm["cached"] is False

    async def broken_fetch(self, params):  # noqa: ANN001 - test stub
        raise ProviderError("arXiv unreachable")

    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", broken_fetch)

    # Cached page still served while offline.
    cached = await client.get(f"/projects/{project_id}/papers/feed?limit=2")
    assert cached.status_code == 200
    assert cached.json()["cached"] is True

    # An uncached page cannot be served -> provider_error envelope.
    miss = await client.get(f"/projects/{project_id}/papers/feed?limit=5")
    assert miss.status_code == 502
    assert miss.json()["error"]["code"] == "provider_error"


async def test_feed_hidden_from_non_members(make_client, arxiv_feed) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "feed-owner@example.com")
    await register(b, email="feed-outsider@example.com")
    resp = await b.get(f"/projects/{project_id}/papers/feed")
    assert resp.status_code == 404
