"""Paper library import/list/isolation tests (providers mocked, no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from researchos.research import service as service_module
from researchos.research.providers import arxiv as arxiv_module

from .helpers import csrf_headers, register

# Import refs carry only source/external_id; metadata is server-verified.
_PAPER = {"source": "arxiv", "external_id": "2401.01234"}


@pytest.fixture
def mocked_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the recorded id_list feed and swallow Celery ingest dispatches."""

    xml = (Path(__file__).parent / "fixtures" / "arxiv_idlist.xml").read_text(encoding="utf-8")

    async def fake_fetch(self, params):  # noqa: ANN001 - test stub
        return xml

    class _NullCelery:
        def send_task(self, name, args=None, queue=None):
            return None

    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", fake_fetch)
    monkeypatch.setattr(service_module, "get_celery_client", lambda: _NullCelery())


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_import_is_idempotent_and_lists(client, mocked_providers) -> None:
    project_id = await _make_project(client, "lib@example.com")

    r1 = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [_PAPER]},
        headers=csrf_headers(client),
    )
    assert r1.status_code == 201
    assert len(r1.json()["imported"]) == 1
    # Re-import the same paper -> no duplicate.
    await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [_PAPER]},
        headers=csrf_headers(client),
    )

    listing = (await client.get(f"/projects/{project_id}/papers")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["external_id"] == "2401.01234"


async def test_search_uses_provider_via_monkeypatch(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "libsearch@example.com")
    xml = (Path(__file__).parent / "fixtures" / "arxiv_sample.xml").read_text(encoding="utf-8")

    async def fake_fetch(self, params):  # noqa: ANN001 - test stub
        return xml

    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", fake_fetch)

    resp = await client.post(
        f"/projects/{project_id}/papers/search",
        json={"query": "vision", "limit": 5},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["source"] == "arxiv"


async def test_library_tenant_isolation(make_client) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "lib-a@example.com")
    await register(b, email="lib-b@example.com")

    resp = await b.get(f"/projects/{project_id}/papers")
    assert resp.status_code == 404
