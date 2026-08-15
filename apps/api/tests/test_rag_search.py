"""Hybrid retrieval (§7.3) tests: RRF fusion, match reasons, filters,
diversity, empty index, limit boundaries, and offset round-trip.

Runs entirely on the local hashing profile (forced by conftest) — no network.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.identity.models import User
from researchos.knowledge.models import PaperChunk
from researchos.knowledge.service import MAX_HITS_PER_PAPER, _rrf_fuse
from researchos.research.enums import PaperIngestStatus, PaperSectionKind
from researchos.research.models import Paper, PaperSection

from .helpers import csrf_headers, register


async def _project(client: AsyncClient, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "RAG"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _add_paper(
    db: AsyncSession,
    project_id: str,
    email: str,
    title: str,
    sections: list[tuple[PaperSectionKind, str, str]],
    *,
    external_id: str | None = None,
) -> Paper:
    user = await db.scalar(select(User).where(User.email == email))
    assert user is not None
    paper = Paper(
        project_id=uuid.UUID(project_id),
        source="arxiv",
        external_id=external_id or f"2601.{uuid.uuid4().int % 100000:05d}",
        title=title,
        abstract=sections[0][2] if sections else "",
        authors_json=["R"],
        url="https://arxiv.org/abs/2601.00000",
        ingest_status=PaperIngestStatus.SUCCEEDED,
        imported_by=user.id,
    )
    db.add(paper)
    await db.flush()
    for seq, (kind, heading, body) in enumerate(sections):
        db.add(
            PaperSection(
                paper_id=paper.id,
                seq=seq,
                level=2,
                heading=heading,
                body=body,
                char_count=len(body),
                kind=kind,
            )
        )
    await db.commit()
    return paper


async def _search(client: AsyncClient, project_id: str, payload: dict) -> dict:
    resp = await client.post(
        f"/projects/{project_id}/rag/search", json=payload, headers=csrf_headers(client)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- pure RRF fusion ---------------------------------------------------------
def test_rrf_fuse_scores_and_ordering() -> None:
    both, vector_only, keyword_only = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    scores = _rrf_fuse([both, vector_only], [both, keyword_only], k=60)

    assert scores[both] == 1 / 61 + 1 / 61  # rank 1 in both legs
    assert scores[vector_only] == 1 / 62  # vector rank 2
    assert scores[keyword_only] == 1 / 62  # keyword rank 2
    assert scores[both] > scores[vector_only]
    assert scores[both] > scores[keyword_only]


# --- filters -----------------------------------------------------------------
async def test_mission_and_kinds_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    email = "rag-filters@example.com"
    project_id = await _project(client, email)
    paper_a = await _add_paper(
        db_session,
        project_id,
        email,
        "Calibrated uncertainty for segmentation",
        [
            (PaperSectionKind.METHOD, "Method", "Epistemic uncertainty calibration ensemble."),
            (PaperSectionKind.RESULTS, "Results", "Calibration error decreases steadily."),
        ],
    )
    await _add_paper(
        db_session,
        project_id,
        email,
        "Uncertainty in database benchmarking",
        [(PaperSectionKind.METHOD, "Method", "Uncertainty quantification for throughput.")],
    )

    unscoped = await _search(client, project_id, {"query": "uncertainty calibration"})
    assert {hit["title"] for hit in unscoped["hits"]} == {
        "Calibrated uncertainty for segmentation",
        "Uncertainty in database benchmarking",
    }

    mission = (
        await client.post(
            f"/projects/{project_id}/missions",
            json={"topic": "Uncertainty", "scope": {"minimum_papers": 1}},
            headers=csrf_headers(client),
        )
    ).json()
    included = await client.post(
        f"/projects/{project_id}/missions/{mission['id']}/papers",
        json={"paper_ids": [str(paper_a.id)], "inclusion_reason": "core"},
        headers=csrf_headers(client),
    )
    assert included.status_code == 201

    scoped = await _search(
        client, project_id, {"query": "uncertainty calibration", "mission_id": mission["id"]}
    )
    assert scoped["hits"]
    assert {hit["title"] for hit in scoped["hits"]} == {
        "Calibrated uncertainty for segmentation"
    }

    methods_only = await _search(
        client, project_id, {"query": "uncertainty calibration", "kinds": ["method"]}
    )
    assert methods_only["hits"]
    assert {hit["kind"] for hit in methods_only["hits"]} == {"method"}


# --- match reasons / keyword leg ---------------------------------------------
async def test_match_reasons_and_partial_keyword_scores(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "rag-reasons@example.com"
    project_id = await _project(client, email)
    await _add_paper(
        db_session,
        project_id,
        email,
        "Uncertainty calibration study",
        [
            (
                PaperSectionKind.METHOD,
                "Method",
                "Our method estimates epistemic uncertainty with a calibration loss.",
            ),
            # No query token overlap -> vector leg only.
            (PaperSectionKind.RESULTS, "Results", "Throughput latency isolation benchmark."),
        ],
    )

    # Multi-word query with only partial token overlap in the text: the old
    # ts_rank_cd keyword leg scored this 0; ts_rank must give partial credit.
    body = await _search(client, project_id, {"query": "epistemic uncertainty bayesian"})
    assert body["mode"] == "hybrid-vector-keyword-v2"
    by_heading = {hit["heading"]: hit for hit in body["hits"]}
    method = by_heading["Method"]
    assert method["match_reasons"] == ["vector", "keyword"]
    assert method["keyword_score"] > 0.0
    assert method["vector_score"] > 0.0
    results = by_heading["Results"]
    assert results["match_reasons"] == ["vector"]
    assert results["keyword_score"] == 0.0


async def test_keyword_only_reason_when_vector_top40_overflows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A keyword match diluted beyond the vector Top-40 keeps a keyword reason."""

    email = "rag-keyword-only@example.com"
    project_id = await _project(client, email)
    fillers = [
        (
            PaperSectionKind.METHOD,
            f"Method {index}",
            f"{'zephyr ' * 8}filler{index} alpha beta gamma delta epsilon zeta eta theta.",
        )
        for index in range(44)
    ]
    diluted = (
        PaperSectionKind.METHOD,
        "Diluted",
        "The zephyr calibration protocol is evaluated. "
        + " ".join(f"distractor{i}" for i in range(60)),
    )
    await _add_paper(db_session, project_id, email, "Zephyr fillers", fillers)
    await _add_paper(db_session, project_id, email, "Zephyr calibration", [diluted])

    body = await _search(client, project_id, {"query": "zephyr calibration", "limit": 50})
    by_title = {hit["title"]: hit for hit in body["hits"]}
    diluted_hit = by_title["Zephyr calibration"]
    assert diluted_hit["match_reasons"] == ["keyword"]
    assert diluted_hit["keyword_score"] > 0.0
    assert diluted_hit["vector_score"] == 0.0
    # Fillers dominate the vector leg; some fall out of the keyword Top-40.
    reasons = {tuple(hit["match_reasons"]) for hit in body["hits"]}
    assert ("vector", "keyword") in reasons
    assert ("vector",) in reasons


# --- empty index / limits / diversity / offsets -------------------------------
async def test_empty_index_returns_wellformed_response(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _project(client, "rag-empty@example.com")
    body = await _search(client, project_id, {"query": "epistemic uncertainty"})
    assert body["hits"] == []
    assert body["indexed_papers"] == 0
    assert body["indexed_chunks"] == 0
    assert body["mode"] == "hybrid-vector-keyword-v2"


async def test_limit_boundaries(client: AsyncClient, db_session: AsyncSession) -> None:
    email = "rag-limit@example.com"
    project_id = await _project(client, email)
    await _add_paper(
        db_session,
        project_id,
        email,
        "Calibration notes",
        [
            (PaperSectionKind.METHOD, "Method", "Calibration of predictive uncertainty."),
            (PaperSectionKind.RESULTS, "Results", "Calibration error reported per dataset."),
            (PaperSectionKind.CONCLUSION, "Conclusion", "Calibration remains challenging."),
        ],
    )
    one = await _search(client, project_id, {"query": "calibration", "limit": 1})
    assert len(one["hits"]) == 1
    wide = await _search(client, project_id, {"query": "calibration", "limit": 50})
    assert 1 < len(wide["hits"]) <= 3


async def test_diversity_caps_hits_per_paper(client: AsyncClient, db_session: AsyncSession) -> None:
    email = "rag-diversity@example.com"
    project_id = await _project(client, email)
    dominant = await _add_paper(
        db_session,
        project_id,
        email,
        "All about calibration",
        [
            (
                PaperSectionKind.METHOD,
                f"Calibration section {index}",
                f"Calibration uncertainty calibration method calibration variant {index}.",
            )
            for index in range(8)
        ],
    )
    other = await _add_paper(
        db_session,
        project_id,
        email,
        "Calibration side notes",
        [(PaperSectionKind.METHOD, "Method", "Calibration uncertainty side notes.")],
    )

    # Within the limit, the per-paper cap holds...
    body = await _search(client, project_id, {"query": "calibration uncertainty", "limit": 4})
    counts: dict[str, int] = {}
    for hit in body["hits"]:
        counts[hit["paper_id"]] = counts.get(hit["paper_id"], 0) + 1
    assert counts.get(str(dominant.id), 0) == MAX_HITS_PER_PAPER
    assert counts.get(str(other.id), 0) == 1
    # ...but a larger limit is filled from the remaining candidates (cap relaxed).
    wide = await _search(client, project_id, {"query": "calibration uncertainty", "limit": 8})
    assert len(wide["hits"]) == 8
    assert sum(1 for hit in wide["hits"] if hit["paper_id"] == str(other.id)) == 1


async def test_hit_offsets_round_trip_into_section_body(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "rag-offsets@example.com"
    project_id = await _project(client, email)
    paper = await _add_paper(
        db_session,
        project_id,
        email,
        "Offset verification",
        [
            (
                PaperSectionKind.METHOD,
                "Method",
                "First sentence on calibration. Second sentence on uncertainty. "
                "Third sentence on evaluation.",
            )
        ],
    )

    body = await _search(client, project_id, {"query": "calibration uncertainty"})
    assert body["hits"]
    for hit in body["hits"]:
        assert hit["paper_id"] == str(paper.id)
        chunk = await db_session.get(PaperChunk, uuid.UUID(hit["chunk_id"]))
        assert chunk is not None
        section = await db_session.get(PaperSection, chunk.section_id)
        assert section is not None
        # Exact offset round-trip into the section body (quote source of truth).
        assert section.body[hit["char_start"] : hit["char_end"]] == chunk.content
        snippet_core = hit["snippet"].strip("…")
        assert snippet_core in " ".join(chunk.content.split())
