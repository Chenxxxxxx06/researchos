"""Server-verified import tests: fabricated metadata is discarded, skips are
reported, cross-source duplicates collapse, and a down broker never fails the
request. No network: provider fetches are monkeypatched with fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from researchos.research import service as service_module
from researchos.research.providers import arxiv as arxiv_module
from researchos.research.providers import openalex as openalex_module
from researchos.research.providers.base import ProviderError

from .helpers import csrf_headers, register

FIXTURES = Path(__file__).parent / "fixtures"
IDLIST_XML = (FIXTURES / "arxiv_idlist.xml").read_text(encoding="utf-8")


@pytest.fixture
def celery_recorder(monkeypatch: pytest.MonkeyPatch) -> list:
    """Record ingest dispatches instead of talking to the broker."""

    sent: list[tuple[str, list, str]] = []

    class _Recorder:
        def send_task(self, name, args=None, queue=None):
            sent.append((name, args or [], queue or ""))

    monkeypatch.setattr(service_module, "get_celery_client", lambda: _Recorder())
    return sent


@pytest.fixture
def arxiv_idlist(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Serve the recorded id_list feed for every arXiv fetch; capture params."""

    calls: list[dict] = []

    async def fake_fetch(self, params):  # noqa: ANN001 - test stub
        calls.append(dict(params))
        return IDLIST_XML

    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", fake_fetch)
    return calls


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_fabricated_metadata_is_discarded(
    client, celery_recorder, arxiv_idlist
) -> None:
    project_id = await _make_project(client, "verify1@example.com")

    # An old-style client echoes a full (fabricated) PaperResult payload.
    fabricated = {
        "source": "arxiv",
        "external_id": "2401.01234",
        "title": "FABRICATED TITLE — I MADE THIS UP",
        "abstract": "Fake abstract",
        "authors": ["Dr. Fake"],
        "venue": "Nature",
        "published_at": None,
        "url": "https://evil.example.org/paper",
        "pdf_url": None,
        "extra": {"injected": True},
    }
    resp = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [fabricated]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["skipped"] == []
    assert len(body["imported"]) == 1
    imported = body["imported"][0]
    # Every displayed field comes from the provider fixture, not the client.
    assert imported["title"] == (
        "Efficient Vision-Language Pretraining for Document Understanding"
    )
    assert imported["url"] == "http://arxiv.org/abs/2401.01234v2"
    assert imported["venue"] == "arXiv"
    assert imported["authors_json"] == ["Alice Researcher", "Bob Scientist"]
    assert imported["doi"] == "10.1234/abc"
    assert imported["arxiv_id"] == "2401.01234"
    assert imported["primary_category"] == "cs.LG"
    assert imported["ingest_status"] == "pending"
    # One batched id_list request, ingestion dispatched for the new paper.
    assert any("id_list" in call for call in arxiv_idlist)
    assert celery_recorder == [
        ("ingestion.paper_fulltext", [imported["id"]], "ingestion")
    ]


async def test_unknown_ids_are_skipped_not_found(
    client, celery_recorder, arxiv_idlist
) -> None:
    project_id = await _make_project(client, "verify2@example.com")
    resp = await client.post(
        f"/projects/{project_id}/papers/import",
        json={
            "papers": [
                {"source": "arxiv", "external_id": "2401.01234"},
                {"source": "arxiv", "external_id": "9999.99999"},
                {"source": "clientdb", "external_id": "whatever"},
            ]
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["imported"]) == 1
    skipped = {(s["source"], s["external_id"]): s["reason"] for s in body["skipped"]}
    assert skipped[("arxiv", "9999.99999")] == "not_found"
    assert skipped[("clientdb", "whatever")] == "invalid_source"


async def test_provider_error_marks_source_skipped(
    client, celery_recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "verify3@example.com")

    async def broken_fetch(self, ids):  # noqa: ANN001 - test stub
        raise ProviderError("arXiv is down")

    monkeypatch.setattr(arxiv_module.ArxivProvider, "fetch_by_ids", broken_fetch)
    resp = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [{"source": "arxiv", "external_id": "2401.01234"}]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201  # never 502: partial success contract
    body = resp.json()
    assert body["imported"] == []
    assert body["skipped"] == [
        {"source": "arxiv", "external_id": "2401.01234", "reason": "provider_error"}
    ]


async def test_reimport_returns_existing_row(client, celery_recorder, arxiv_idlist) -> None:
    project_id = await _make_project(client, "verify4@example.com")
    payload = {"papers": [{"source": "arxiv", "external_id": "2401.01234"}]}

    first = await client.post(
        f"/projects/{project_id}/papers/import", json=payload, headers=csrf_headers(client)
    )
    second = await client.post(
        f"/projects/{project_id}/papers/import", json=payload, headers=csrf_headers(client)
    )
    assert second.status_code == 201
    assert second.json()["imported"][0]["id"] == first.json()["imported"][0]["id"]

    listing = (await client.get(f"/projects/{project_id}/papers")).json()
    assert listing["total"] == 1
    # Ingestion dispatched only for the genuinely new row.
    assert len(celery_recorder) == 1


async def test_cross_source_doi_dedup(
    client, celery_recorder, arxiv_idlist, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "verify5@example.com")

    # 1. Import from arXiv (fixture carries doi 10.1234/abc).
    first = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [{"source": "arxiv", "external_id": "2401.01234"}]},
        headers=csrf_headers(client),
    )
    arxiv_row_id = first.json()["imported"][0]["id"]

    # 2. The same paper arrives as an OpenAlex reference.
    import json as _json

    work = _json.loads((FIXTURES / "openalex_work.json").read_text(encoding="utf-8"))

    async def fake_fetch_by_ids(self, ids):  # noqa: ANN001 - test stub
        return [openalex_module._item_to_result(work)]

    monkeypatch.setattr(openalex_module.OpenAlexProvider, "fetch_by_ids", fake_fetch_by_ids)
    second = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [{"source": "openalex", "external_id": "W2741809807"}]},
        headers=csrf_headers(client),
    )
    assert second.status_code == 201
    body = second.json()
    assert body["skipped"] == []
    # The existing arXiv row is returned; no second row is created.
    assert body["imported"][0]["id"] == arxiv_row_id
    listing = (await client.get(f"/projects/{project_id}/papers")).json()
    assert listing["total"] == 1


async def test_import_survives_broker_down(
    client, arxiv_idlist, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project(client, "verify6@example.com")

    def broken_celery():
        raise ConnectionError("broker down")

    monkeypatch.setattr(service_module, "get_celery_client", broken_celery)
    resp = await client.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [{"source": "arxiv", "external_id": "2401.01234"}]},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    imported = resp.json()["imported"]
    assert len(imported) == 1
    # Paper stays pending; the re-trigger endpoint can recover later.
    assert imported[0]["ingest_status"] == "pending"


async def test_import_requires_researcher_role(make_client, arxiv_idlist) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "verify7-a@example.com")
    await register(b, email="verify7-b@example.com")

    resp = await b.post(
        f"/projects/{project_id}/papers/import",
        json={"papers": [{"source": "arxiv", "external_id": "2401.01234"}]},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404  # tenancy hides the project entirely
