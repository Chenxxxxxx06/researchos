"""Full-text ingestion tests: ar5iv parsing, fallbacks, idempotency, the
sections endpoint, the agent tool shape, and WS event publishing.

No network (fixture-backed transports) and no Celery (direct session calls).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.identity.models import User
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.research import ingest as ingest_module
from researchos.research import service as service_module
from researchos.research.enums import PaperIngestStatus, PaperSectionKind
from researchos.research.ingest import ingest_paper_with_session, parse_ar5iv_html
from researchos.research.models import Paper
from researchos.research.repository import PaperRepository, PaperSectionRepository
from researchos.research.service import PaperService

from .helpers import csrf_headers, register

FIXTURES = Path(__file__).parent / "fixtures"
AR5IV_HTML = (FIXTURES / "ar5iv_sample.html").read_text(encoding="utf-8")


def _ar5iv_client(status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if status_code == 200 and request.url.host == "ar5iv.labs.arxiv.org":
            return httpx.Response(200, text=AR5IV_HTML)
        return httpx.Response(status_code, text="not found")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _setup_paper(
    db: AsyncSession,
    email: str,
    *,
    source: str = "arxiv",
    external_id: str = "2401.01234",
    arxiv_id: str | None = "2401.01234",
    abstract: str | None = "Seed abstract for fallback.",
):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Ingest"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    paper = await PaperRepository(db).create(
        Paper(
            project_id=project.id,
            source=source,
            external_id=external_id,
            title="Efficient Vision-Language Pretraining for Document Understanding",
            abstract=abstract,
            authors_json=["Alice Researcher"],
            url=f"http://arxiv.org/abs/{external_id}",
            arxiv_id=arxiv_id,
            imported_by=user.id,
        )
    )
    await db.commit()
    return user, project, paper


# --- parser unit -------------------------------------------------------------
def test_parse_ar5iv_html_sections_and_kinds() -> None:
    sections = parse_ar5iv_html(AR5IV_HTML, max_chars=20_000)

    assert len(sections) == 7  # abstract + 5 sections + appendix
    assert sections[0].kind is PaperSectionKind.ABSTRACT
    assert sections[0].seq == 0 and sections[0].level == 1
    kinds = [s.kind for s in sections]
    assert PaperSectionKind.INTRODUCTION in kinds
    assert PaperSectionKind.METHOD in kinds
    assert PaperSectionKind.EXPERIMENTS in kinds
    assert PaperSectionKind.RESULTS in kinds
    assert PaperSectionKind.CONCLUSION in kinds
    assert PaperSectionKind.APPENDIX in kinds

    intro = next(s for s in sections if s.kind is PaperSectionKind.INTRODUCTION)
    assert intro.heading == "Introduction"  # numbering stripped, word intact
    assert intro.level == 2
    # Subsection content is flattened into the parent body.
    assert "Motivation" in intro.body and "affordable pretraining" in intro.body

    method = next(s for s in sections if s.kind is PaperSectionKind.METHOD)
    assert "L=L_m" in method.body  # inline math replaced by alttext
    # Display math keeps its alttext too (LaTeX preserved verbatim); the raw
    # symbol markup text is dropped in favor of the alttext.
    assert r"\frac{1}{\sqrt{d_k}}" in method.body
    assert "DISPLAY_EQUATION_GIBBERISH" not in method.body
    assert "FIGURE_CAPTION_TO_DROP" not in method.body
    assert all("BIBLIOGRAPHY_ENTRY_TO_DROP" not in s.body for s in sections)


def test_parse_ar5iv_html_truncates_bodies() -> None:
    sections = parse_ar5iv_html(AR5IV_HTML, max_chars=40)
    assert all(len(s.body) <= 40 for s in sections)


_NORMALIZATION_HTML = """
<html><body><article>
<section class="ltx_section" id="S1">
  <h2 class="ltx_title ltx_title_section"><span class="ltx_tag">3 </span>Training Details</h2>
  <div class="ltx_para"><p class="ltx_p">Prior work
  <sup>[</sup><sup>5</sup><sup>,</sup><sup>2</sup><sup>,</sup><sup>35</sup><sup>]</sup> shows gains.
  The loss <math alttext="\\mathcal{L}=\\frac{1}{N}\\sum_i \\ell_i.">
  <semantics><mrow><mi>L</mi></mrow></semantics></math> . is minimized.</p></div>
  <table class="ltx_equation" id="S1.E1"><tr><td class="ltx_eqn_cell">
  <math display="block"><semantics><mrow><mi>E</mi><mo>=</mo><mi>m</mi>
  <msup><mi>c</mi><mn>2</mn></msup></mrow></semantics></math>
  </td></tr></table>
</section>
</article></body></html>
"""


def test_parse_ar5iv_html_normalizes_body_and_classifies_training() -> None:
    (section,) = parse_ar5iv_html(_NORMALIZATION_HTML, max_chars=20_000)

    # "training" heading -> experiments kind.
    assert section.kind is PaperSectionKind.EXPERIMENTS
    # Fluent text: no fragmented newlines anywhere in the body.
    assert "\n" not in section.body
    # Citation markers fragmented by inline tags collapse to [5,2,35].
    assert "[5,2,35]" in section.body
    # LaTeX alttext is preserved verbatim; the double period left by the
    # math replacement (". .") collapses to a single period.
    assert r"\mathcal{L}=\frac{1}{N}\sum_i \ell_i." in section.body
    assert ". ." not in section.body
    # Display math without alttext keeps its symbol text instead of vanishing.
    assert "E = m c 2" in section.body


# --- ingest paths ------------------------------------------------------------
async def test_ingest_succeeds_and_is_idempotent(db_session: AsyncSession) -> None:
    _, _, paper = await _setup_paper(db_session, "ingest1@example.com")

    async with _ar5iv_client() as http:
        status = await ingest_paper_with_session(db_session, paper.id, http_client=http)
    assert status is PaperIngestStatus.SUCCEEDED

    await db_session.refresh(paper)
    assert paper.ingest_status is PaperIngestStatus.SUCCEEDED
    assert paper.ingested_at is not None
    rows = await PaperSectionRepository(db_session).list_by_paper(paper.id)
    assert len(rows) >= 5
    assert [r.seq for r in rows] == list(range(len(rows)))
    assert all(r.char_count == len(r.body) for r in rows)
    kinds = {r.kind for r in rows}
    assert {
        PaperSectionKind.INTRODUCTION,
        PaperSectionKind.METHOD,
        PaperSectionKind.EXPERIMENTS,
        PaperSectionKind.APPENDIX,
    } <= kinds

    # Re-ingest (acks_late redelivery) fully replaces rows, no duplicates.
    async with _ar5iv_client() as http:
        await ingest_paper_with_session(db_session, paper.id, http_client=http)
    rows_again = await PaperSectionRepository(db_session).list_by_paper(paper.id)
    assert len(rows_again) == len(rows)


async def test_ingest_without_arxiv_id_falls_back_to_abstract(
    db_session: AsyncSession,
) -> None:
    _, _, paper = await _setup_paper(
        db_session,
        "ingest2@example.com",
        source="s2",
        external_id="649def34",
        arxiv_id=None,
    )
    status = await ingest_paper_with_session(db_session, paper.id)
    assert status is PaperIngestStatus.ABSTRACT_ONLY

    rows = await PaperSectionRepository(db_session).list_by_paper(paper.id)
    assert len(rows) == 1
    assert rows[0].kind is PaperSectionKind.ABSTRACT
    assert rows[0].body == "Seed abstract for fallback."


async def test_ingest_fetch_failure_falls_back_or_fails(db_session: AsyncSession) -> None:
    _, _, with_abstract = await _setup_paper(db_session, "ingest3@example.com")
    async with _ar5iv_client(status_code=404) as http:
        status = await ingest_paper_with_session(db_session, with_abstract.id, http_client=http)
    assert status is PaperIngestStatus.ABSTRACT_ONLY

    _, _, without_abstract = await _setup_paper(
        db_session, "ingest4@example.com", external_id="2312.05678",
        arxiv_id="2312.05678", abstract=None,
    )
    async with _ar5iv_client(status_code=404) as http:
        status = await ingest_paper_with_session(
            db_session, without_abstract.id, http_client=http
        )
    assert status is PaperIngestStatus.FAILED
    await db_session.refresh(without_abstract)
    assert without_abstract.ingest_error
    assert len(without_abstract.ingest_error) <= 500


async def test_ingest_publishes_ws_events(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, project, paper = await _setup_paper(db_session, "ingest5@example.com")
    published: list[tuple[str, dict]] = []

    async def record(project_id: str, envelope: dict) -> None:
        published.append((project_id, envelope))

    monkeypatch.setattr(ingest_module, "publish_event", record)

    async with _ar5iv_client() as http:
        await ingest_paper_with_session(db_session, paper.id, http_client=http)

    types = [envelope["event_type"] for _, envelope in published]
    assert types == ["paper.ingest.started", "paper.ingest.completed"]
    for project_id, envelope in published:
        assert project_id == str(project.id)
        assert envelope["resource_type"] == "paper"
        assert envelope["resource_id"] == str(paper.id)
    completed = published[-1][1]["payload"]
    assert completed["status"] == "succeeded"
    assert completed["section_count"] >= 5


# --- endpoints ---------------------------------------------------------------
async def _make_project_via_api(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _insert_paper(db: AsyncSession, project_id: str, email: str) -> Paper:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    paper = await PaperRepository(db).create(
        Paper(
            project_id=uuid.UUID(project_id),
            source="arxiv",
            external_id="2401.01234",
            title="Efficient Vision-Language Pretraining for Document Understanding",
            abstract="Seed abstract.",
            authors_json=[],
            url="http://arxiv.org/abs/2401.01234",
            arxiv_id="2401.01234",
            imported_by=user.id,
        )
    )
    await db.commit()
    return paper


async def test_sections_endpoint_and_tenancy(client, make_client, db_session) -> None:
    project_id = await _make_project_via_api(client, "sections@example.com")
    paper = await _insert_paper(db_session, project_id, "sections@example.com")
    async with _ar5iv_client() as http:
        await ingest_paper_with_session(db_session, paper.id, http_client=http)

    resp = await client.get(f"/projects/{project_id}/papers/{paper.id}/sections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingest_status"] == "succeeded"
    assert body["paper_id"] == str(paper.id)
    assert len(body["sections"]) >= 5
    assert body["sections"][0]["kind"] == "abstract"
    assert body["sections"][0]["seq"] == 0

    outsider = make_client()
    await register(outsider, email="sections-outsider@example.com")
    resp = await outsider.get(f"/projects/{project_id}/papers/{paper.id}/sections")
    assert resp.status_code == 404


async def test_ingest_trigger_endpoint(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = await _make_project_via_api(client, "trigger@example.com")
    paper = await _insert_paper(db_session, project_id, "trigger@example.com")

    sent: list[tuple[str, list, str]] = []

    class _Recorder:
        def send_task(self, name, args=None, queue=None):
            sent.append((name, args or [], queue or ""))

    monkeypatch.setattr(service_module, "get_celery_client", lambda: _Recorder())

    resp = await client.post(
        f"/projects/{project_id}/papers/{paper.id}/ingest", headers=csrf_headers(client)
    )
    assert resp.status_code == 202
    assert resp.json()["ingest_status"] == "pending"
    assert sent == [("ingestion.paper_fulltext", [str(paper.id)], "ingestion")]

    # A running ingest cannot be re-triggered.
    paper.ingest_status = PaperIngestStatus.RUNNING
    await db_session.commit()
    resp = await client.post(
        f"/projects/{project_id}/papers/{paper.id}/ingest", headers=csrf_headers(client)
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ingest_running"


# --- agent tool shape --------------------------------------------------------
async def test_sections_for_agent_tool_shape(db_session: AsyncSession) -> None:
    user, project, paper = await _setup_paper(db_session, "tool@example.com")
    async with _ar5iv_client() as http:
        await ingest_paper_with_session(db_session, paper.id, http_client=http)

    service = PaperService(db_session)
    out = await service.sections_for_agent(
        user, project.id, paper_key="arxiv:2401.01234"
    )
    assert out["ingest_status"] == "succeeded"
    assert len(out["results"]) >= 5
    first = out["results"][0]
    # source/external_id present -> ToolBroker whitelists the citation.
    assert first["source"] == "arxiv" and first["external_id"] == "2401.01234"
    assert {"title", "url", "seq", "heading", "kind", "level", "body"} <= set(first)
    assert all(len(item["body"]) <= 2000 for item in out["results"])

    only_method = await service.sections_for_agent(
        user, project.id, paper_key="arxiv:2401.01234", kind="method"
    )
    assert only_method["results"]
    assert all(item["kind"] == "method" for item in only_method["results"])

    by_seq = await service.sections_for_agent(
        user, project.id, paper_key="arxiv:2401.01234", seq=0
    )
    assert [item["seq"] for item in by_seq["results"]] == [0]


async def test_sections_for_agent_degrades_gracefully(db_session: AsyncSession) -> None:
    user, project, paper = await _setup_paper(
        db_session, "tool2@example.com", external_id="2350.00001", arxiv_id="2350.00001"
    )
    service = PaperService(db_session)

    # Un-ingested paper -> abstract pseudo-section plus pending status.
    out = await service.sections_for_agent(user, project.id, paper_key="arxiv:2350.00001")
    assert out["ingest_status"] == "pending"
    assert len(out["results"]) == 1
    assert out["results"][0]["kind"] == "abstract"

    # Unknown key -> empty results, not an exception.
    missing = await service.sections_for_agent(user, project.id, paper_key="arxiv:nope")
    assert missing["results"] == []
    assert "error" in missing
