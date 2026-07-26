"""Gap-matrix idea generation: deterministic mining + mock-LLM e2e persistence.

The mock provider returns one idea citing keys from the tool-shaped context
message, so persisted ideas always carry validated library citations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.identity.models import User
from researchos.research.gap_matrix import GapDoc, _terms_of, build_gap_matrix, first_sentences
from researchos.research.models import Paper

from .helpers import csrf_headers, register


# --- deterministic mining ----------------------------------------------------
def test_terms_of_includes_bigrams_and_first_sentences() -> None:
    terms = _terms_of("Diffusion models for planning")
    assert "diffusion" in terms
    assert "diffusion models" in terms  # bigram
    assert "for" not in terms  # stopword

    text = "First sentence here. Second one! Third is dropped."
    assert first_sentences(text) == "First sentence here. Second one!"


def _doc(key: str, method: str, problem: str) -> GapDoc:
    return GapDoc(
        key=key, title=key, method_terms=_terms_of(method), problem_terms=_terms_of(problem)
    )


def test_build_gap_matrix_mines_uncovered_cells_deterministically() -> None:
    docs = [
        # "diffusion" methods applied only to image problems.
        _doc("a1", "diffusion sampling", "image synthesis quality"),
        _doc("a2", "diffusion sampling", "image restoration quality"),
        # "graph" methods applied only to protein problems.
        _doc("b1", "graph encoder", "protein folding structure"),
        _doc("b2", "graph encoder", "protein binding structure"),
    ]
    matrix = build_gap_matrix(docs)

    assert matrix.method_support["diffusion"] == 2
    assert matrix.problem_support["protein"] == 2
    gap_pairs = {(cell.method, cell.problem) for cell in matrix.gaps}
    # Cross pairings are gaps; within-cluster pairings are covered.
    assert ("diffusion", "protein") in gap_pairs
    assert ("graph", "image") in gap_pairs or ("graph", "quality") in gap_pairs
    assert ("diffusion", "image") not in gap_pairs
    assert ("graph", "protein") not in gap_pairs
    # Bounded, weight-ranked, deterministic.
    assert len(matrix.gaps) <= 10
    weights = [cell.weight for cell in matrix.gaps]
    assert weights == sorted(weights, reverse=True)
    again = build_gap_matrix(docs)
    assert [(c.method, c.problem, c.weight) for c in again.gaps] == [
        (c.method, c.problem, c.weight) for c in matrix.gaps
    ]


def test_build_gap_matrix_requires_two_paper_support() -> None:
    docs = [
        _doc("a", "unique-method-term alpha shared", "shared problem"),
        _doc("b", "beta shared", "shared problem"),
    ]
    matrix = build_gap_matrix(docs)
    # Terms appearing in a single paper never become axis terms.
    assert "alpha" not in matrix.method_terms
    assert "beta" not in matrix.method_terms
    assert "shared" in matrix.method_terms


# --- e2e with the mock provider ----------------------------------------------
async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def _seed_library(db: AsyncSession, project_id: str, email: str) -> list[str]:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    corpus = [
        (
            "2401.00001",
            "Diffusion models for planning",
            "We study diffusion planning. Image domains.",
        ),
        (
            "2401.00002",
            "Diffusion models for control",
            "We study diffusion control. Image domains.",
        ),
        ("2401.00003", "Graph networks for chemistry", "Protein folding analysis. Molecules."),
        ("2401.00004", "Graph networks for physics", "Protein binding analysis. Molecules."),
        ("2401.00005", "Transformers for language", "Text corpora at scale. Tokens."),
    ]
    keys = []
    for external_id, title, abstract in corpus:
        db.add(
            Paper(
                project_id=uuid.UUID(project_id),
                source="arxiv",
                external_id=external_id,
                title=title,
                abstract=abstract,
                authors_json=[],
                url=f"http://arxiv.org/abs/{external_id}",
                imported_by=user.id,
            )
        )
        keys.append(f"arxiv:{external_id}")
    await db.commit()
    return keys


async def test_generate_persists_ideas_with_validated_keys(client, db_session) -> None:
    project_id = await _make_project(client, "gap1@example.com")
    library_keys = await _seed_library(db_session, project_id, "gap1@example.com")

    resp = await client.post(
        f"/projects/{project_id}/ideas/generate",
        json={"max_ideas": 3},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["papers_used"] == 5
    assert body["gaps_considered"] >= 1
    assert len(body["ideas"]) >= 1

    idea = body["ideas"][0]
    assert idea["status"] == "draft"
    assert idea["title"]
    metadata = idea["metadata"]
    assert metadata["generated"] is True
    assert metadata["gap_type"] == "coverage"
    keys = metadata["supporting_paper_keys"]
    assert keys and all(key in library_keys for key in keys)

    # Persisted: the idea shows up in the normal list with its metadata.
    listing = (await client.get(f"/projects/{project_id}/ideas")).json()
    listed = {i["id"]: i for i in listing["items"]}
    assert idea["id"] in listed
    assert listed[idea["id"]]["metadata"]["supporting_paper_keys"] == keys


async def test_generate_conflicts_when_library_too_small(client, db_session) -> None:
    project_id = await _make_project(client, "gap2@example.com")
    resp = await client.post(
        f"/projects/{project_id}/ideas/generate",
        json={"max_ideas": 2},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "library_too_small"


async def test_generate_validates_max_ideas(client) -> None:
    project_id = await _make_project(client, "gap3@example.com")
    for bad in (0, 6):
        resp = await client.post(
            f"/projects/{project_id}/ideas/generate",
            json={"max_ideas": bad},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 422


async def test_generate_hidden_from_non_members(make_client, db_session) -> None:
    a = make_client()
    b = make_client()
    project_id = await _make_project(a, "gap4-a@example.com")
    await _seed_library(db_session, project_id, "gap4-a@example.com")
    await register(b, email="gap4-b@example.com")

    resp = await b.post(
        f"/projects/{project_id}/ideas/generate",
        json={"max_ideas": 1},
        headers=csrf_headers(b),
    )
    assert resp.status_code == 404
