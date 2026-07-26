"""Citation listing and BibTeX insertion endpoints (DB, CI)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.research.models import Paper

from .helpers import csrf_headers, register


async def _paper_project(client, email: str) -> tuple[str, str, str]:
    reg = await register(client, email=email)
    user_id = reg["user"]["id"]
    org_id = (await client.get("/organizations")).json()[0]["id"]
    h = csrf_headers(client)
    project_id = (
        await client.post("/projects", json={"organization_id": org_id, "name": "P"}, headers=h)
    ).json()["id"]
    lp_id = (
        await client.post(
            f"/projects/{project_id}/latex-projects", json={"name": "Paper"}, headers=h
        )
    ).json()["id"]
    return project_id, lp_id, user_id


async def _seed_papers(db: AsyncSession, project_id: str, user_id: str) -> tuple[Paper, Paper]:
    arxiv = Paper(
        project_id=uuid.UUID(project_id),
        source="arxiv",
        external_id="1706.03762",
        title="Attention Is All You Need",
        authors_json=["Ashish Vaswani", "Noam Shazeer"],
        published_at=datetime(2017, 6, 12, tzinfo=UTC),
        url="https://arxiv.org/abs/1706.03762",
        imported_by=uuid.UUID(user_id),
    )
    venue = Paper(
        project_id=uuid.UUID(project_id),
        source="openalex",
        external_id="W2100837269",
        title="Deep Residual Learning for Image Recognition",
        authors_json=["Kaiming He"],
        venue="CVPR",
        published_at=datetime(2016, 6, 27, tzinfo=UTC),
        url="https://example.org/resnet",
        imported_by=uuid.UUID(user_id),
    )
    db.add_all([arxiv, venue])
    await db.commit()
    return arxiv, venue


def _base(p: str, lp: str) -> str:
    return f"/projects/{p}/latex-projects/{lp}"


async def test_citation_list_and_insert_roundtrip(client, db_session: AsyncSession) -> None:
    p, lp, user_id = await _paper_project(client, "cit-round@example.com")
    arxiv, _ = await _seed_papers(db_session, p, user_id)
    h = csrf_headers(client)

    listing = (await client.get(f"{_base(p, lp)}/citations")).json()
    assert listing["total"] == 2
    by_key = {item["cite_key"]: item for item in listing["items"]}
    assert by_key["vaswani2017attention"]["in_bib"] is False
    assert by_key["vaswani2017attention"]["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert by_key["vaswani2017attention"]["year"] == 2017
    assert "he2016deep" in by_key

    resp = await client.post(
        f"{_base(p, lp)}/citations/insert", json={"paper_id": str(arxiv.id)}, headers=h
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cite_key"] == "vaswani2017attention"
    assert body["snippet"] == "\\cite{vaswani2017attention}"
    assert body["entry_added"] is True
    assert body["bibliography_command_added"] is True
    assert body["bib_file"] == {"path": "refs.bib", "version": 1}

    bib = (
        await client.get(f"{_base(p, lp)}/files/content?path=refs.bib")
    ).json()
    assert "@misc{vaswani2017attention," in bib["content"]
    assert "eprint = {1706.03762}" in bib["content"]

    main = (
        await client.get(f"{_base(p, lp)}/files/content?path=main.tex")
    ).json()
    assert "\\bibliographystyle{plain}" in main["content"]
    assert "\\bibliography{refs}" in main["content"]
    # The bibliography block sits before \end{document}.
    assert main["content"].index("\\bibliography{refs}") < main["content"].index("\\end{document}")

    # in_bib flips on the next listing.
    listing2 = (await client.get(f"{_base(p, lp)}/citations")).json()
    by_key2 = {item["cite_key"]: item for item in listing2["items"]}
    assert by_key2["vaswani2017attention"]["in_bib"] is True


async def test_citation_insert_idempotent(client, db_session: AsyncSession) -> None:
    p, lp, user_id = await _paper_project(client, "cit-idem@example.com")
    arxiv, _ = await _seed_papers(db_session, p, user_id)
    h = csrf_headers(client)

    first = (
        await client.post(
            f"{_base(p, lp)}/citations/insert", json={"paper_id": str(arxiv.id)}, headers=h
        )
    ).json()
    assert first["entry_added"] is True

    second = (
        await client.post(
            f"{_base(p, lp)}/citations/insert", json={"paper_id": str(arxiv.id)}, headers=h
        )
    ).json()
    assert second["cite_key"] == "vaswani2017attention"
    assert second["entry_added"] is False
    assert second["bibliography_command_added"] is False
    assert second["bib_file"]["version"] == 1  # untouched

    bib = (
        await client.get(f"{_base(p, lp)}/files/content?path=refs.bib")
    ).json()
    assert bib["content"].count("@misc{vaswani2017attention,") == 1


async def test_citation_insert_cas_conflict_on_bib(client, db_session: AsyncSession) -> None:
    p, lp, user_id = await _paper_project(client, "cit-cas@example.com")
    arxiv, venue = await _seed_papers(db_session, p, user_id)
    h = csrf_headers(client)

    await client.post(
        f"{_base(p, lp)}/citations/insert", json={"paper_id": str(arxiv.id)}, headers=h
    )
    stale = await client.post(
        f"{_base(p, lp)}/citations/insert",
        json={"paper_id": str(venue.id), "expected_bib_version": 99},
        headers=h,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "document_version_conflict"


async def test_citation_insert_unknown_paper_404(client) -> None:
    p, lp, _ = await _paper_project(client, "cit-404@example.com")
    h = csrf_headers(client)
    resp = await client.post(
        f"{_base(p, lp)}/citations/insert", json={"paper_id": str(uuid.uuid4())}, headers=h
    )
    assert resp.status_code == 404
