"""Paper delete preflight: reference counts, 409 guard, and force delete."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.experiment_plans.models import ExperimentPlan
from researchos.identity.models import User
from researchos.research.enums import PaperIngestStatus
from researchos.research.models import Idea, Paper, ResearchCritique
from researchos.reviews.models import ReviewDocument, ReviewSection

from .helpers import csrf_headers, register

_EMAIL = "delete-refs@example.com"


async def _setup(client: AsyncClient, db: AsyncSession) -> tuple[dict, dict, Paper, User]:
    """Project + mission + one library paper, no downstream artifacts yet."""

    await register(client, email=_EMAIL)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = (
        await client.post(
            "/projects",
            json={"organization_id": org_id, "name": "Delete Refs Project"},
            headers=csrf_headers(client),
        )
    ).json()
    mission = (
        await client.post(
            f"/projects/{project['id']}/missions",
            json={"topic": "Citation safety", "scope": {"minimum_papers": 1}},
            headers=csrf_headers(client),
        )
    ).json()
    user = await db.scalar(select(User).where(User.email == _EMAIL))
    assert user is not None
    paper = Paper(
        project_id=uuid.UUID(project["id"]),
        source="arxiv",
        external_id="2601.99999",
        title="A paper referenced everywhere",
        abstract="References preflight test fixture.",
        authors_json=["Researcher B"],
        url="https://arxiv.org/abs/2601.99999",
        ingest_status=PaperIngestStatus.PENDING,
        imported_by=user.id,
    )
    db.add(paper)
    await db.commit()
    return project, mission, paper, user


async def _add_all_references(
    client: AsyncClient, db: AsyncSession, project: dict, mission: dict, paper: Paper, user: User
) -> None:
    """Create exactly one referencing artifact per category."""

    base = f"/projects/{project['id']}"
    mission_id = uuid.UUID(mission["id"])

    included = await client.post(
        f"{base}/missions/{mission['id']}/papers",
        json={"paper_ids": [str(paper.id)], "inclusion_reason": "Core"},
        headers=csrf_headers(client),
    )
    assert included.status_code == 201

    card = await client.put(
        f"{base}/papers/{paper.id}/reading-card",
        json={"mission_id": mission["id"], "summary": "Referenced."},
        headers=csrf_headers(client),
    )
    assert card.status_code == 200

    note = await client.post(
        f"{base}/papers/{paper.id}/notes",
        json={"mission_id": mission["id"], "content": "A note on the paper."},
        headers=csrf_headers(client),
    )
    assert note.status_code == 201

    review = ReviewDocument(
        project_id=paper.project_id,
        mission_id=mission_id,
        title="Demo review",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(review)
    await db.flush()
    db.add(
        ReviewSection(
            project_id=paper.project_id,
            mission_id=mission_id,
            review_id=review.id,
            section_key="related-work",
            position=1,
            title="Related work",
            citations_json=[str(paper.id)],
            claims_json=[{"text": "It works.", "paper_id": str(paper.id)}],
            updated_by=user.id,
        )
    )
    db.add(
        ExperimentPlan(
            project_id=paper.project_id,
            mission_id=mission_id,
            title="Demo plan",
            baselines_json=[
                {
                    "name": "baseline",
                    "source_paper_id": str(paper.id),
                    "evidence_status": "grounded",
                }
            ],
            created_by=user.id,
            updated_by=user.id,
        )
    )
    idea = Idea(
        project_id=paper.project_id,
        title="Referenced idea",
        description="Critique reference fixture.",
        created_by=user.id,
    )
    db.add(idea)
    await db.flush()
    db.add(
        ResearchCritique(
            project_id=paper.project_id,
            idea_id=idea.id,
            novelty_summary="Grounded critique",
            citations_json=[str(paper.id)],
        )
    )
    await db.commit()


async def test_delete_without_references_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project, _, paper, _ = await _setup(client, db_session)
    base = f"/projects/{project['id']}/papers/{paper.id}"

    preflight = await client.get(f"{base}/references")
    assert preflight.status_code == 200
    assert preflight.json() == {
        "paper_id": str(paper.id),
        "references": {
            "reading_cards": 0,
            "reading_notes": 0,
            "review_sections": 0,
            "research_critiques": 0,
            "experiment_plans": 0,
            "missions": 0,
        },
        "blocked": False,
    }

    deleted = await client.delete(base, headers=csrf_headers(client))
    assert deleted.status_code == 204
    assert (await client.get(base)).status_code == 404


async def test_references_preflight_counts(client: AsyncClient, db_session: AsyncSession) -> None:
    project, mission, paper, user = await _setup(client, db_session)
    await _add_all_references(client, db_session, project, mission, paper, user)

    resp = await client.get(f"/projects/{project['id']}/papers/{paper.id}/references")
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_id"] == str(paper.id)
    assert body["references"] == {
        "reading_cards": 1,
        "reading_notes": 1,
        "review_sections": 1,
        "research_critiques": 1,
        "experiment_plans": 1,
        "missions": 1,
    }
    assert body["blocked"] is True


async def test_delete_with_references_returns_409_with_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project, mission, paper, user = await _setup(client, db_session)
    await _add_all_references(client, db_session, project, mission, paper, user)
    base = f"/projects/{project['id']}/papers/{paper.id}"

    resp = await client.delete(base, headers=csrf_headers(client))
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "paper_has_references"
    assert error["details"]["references"] == {
        "reading_cards": 1,
        "reading_notes": 1,
        "review_sections": 1,
        "research_critiques": 1,
        "experiment_plans": 1,
        "missions": 1,
    }
    # The paper survives a blocked delete.
    assert (await client.get(base)).status_code == 200


async def test_delete_force_removes_referenced_paper(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project, mission, paper, user = await _setup(client, db_session)
    await _add_all_references(client, db_session, project, mission, paper, user)
    base = f"/projects/{project['id']}/papers/{paper.id}"

    deleted = await client.delete(base, params={"force": "true"}, headers=csrf_headers(client))
    assert deleted.status_code == 204
    assert (await client.get(base)).status_code == 404
