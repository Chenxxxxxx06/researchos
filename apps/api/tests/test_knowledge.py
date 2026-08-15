"""Mission paper knowledge, reading card, note, clustering, and retrieval tests."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.llm.mock import MockLLMProvider
from researchos.agents.runtime.runtime import AgentRuntime
from researchos.identity.models import User
from researchos.knowledge.indexing import ensure_project_chunks
from researchos.knowledge.models import PaperChunk
from researchos.knowledge.profiles import get_active_profile
from researchos.research.enums import PaperIngestStatus, PaperSectionKind
from researchos.research.models import Paper, PaperSection

from .helpers import csrf_headers, register


async def _setup(client: AsyncClient, db: AsyncSession) -> tuple[dict, dict, Paper, PaperSection]:
    await register(client, email="knowledge@example.com")
    org_id = (await client.get("/organizations")).json()[0]["id"]
    project = (
        await client.post(
            "/projects",
            json={"organization_id": org_id, "name": "Knowledge Project"},
            headers=csrf_headers(client),
        )
    ).json()
    mission = (
        await client.post(
            f"/projects/{project['id']}/missions",
            json={"topic": "Uncertainty estimation", "scope": {"minimum_papers": 1}},
            headers=csrf_headers(client),
        )
    ).json()
    user = await db.scalar(select(User).where(User.email == "knowledge@example.com"))
    assert user is not None
    paper = Paper(
        project_id=uuid.UUID(project["id"]),
        source="arxiv",
        external_id="2601.12345",
        title="Calibrated uncertainty for weakly supervised segmentation",
        abstract="We study calibration in medical image segmentation.",
        authors_json=["Researcher A"],
        venue="MICCAI",
        url="https://arxiv.org/abs/2601.12345",
        primary_category="cs.CV",
        ingest_status=PaperIngestStatus.SUCCEEDED,
        imported_by=user.id,
    )
    db.add(paper)
    await db.flush()
    section = PaperSection(
        paper_id=paper.id,
        seq=1,
        level=2,
        heading="Method",
        body="Our method estimates epistemic uncertainty with an ensemble and calibration loss.",
        char_count=81,
        kind=PaperSectionKind.METHOD,
    )
    db.add(section)
    await db.commit()
    return project, mission, paper, section


async def test_mission_knowledge_end_to_end(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    project, mission, paper, section = await _setup(client, db_session)
    base = f"/projects/{project['id']}"

    included = await client.post(
        f"{base}/missions/{mission['id']}/papers",
        json={"paper_ids": [str(paper.id)], "inclusion_reason": "Core method"},
        headers=csrf_headers(client),
    )
    assert included.status_code == 201
    assert included.json()[0]["title"] == paper.title

    search = await client.post(
        f"{base}/rag/search",
        json={"query": "epistemic uncertainty", "mission_id": mission["id"]},
        headers=csrf_headers(client),
    )
    assert search.status_code == 200
    assert search.json()["mode"] == "hybrid-vector-keyword-v2"
    assert search.json()["embedding_model"] == "hashing-1024-v2"
    assert search.json()["hits"][0]["section_id"] == str(section.id)

    clustered = await client.post(
        f"{base}/missions/{mission['id']}/cluster", headers=csrf_headers(client)
    )
    assert clustered.status_code == 200
    cluster = clustered.json()[0]
    assert "uncertainty" in cluster["name"]
    assert "uncertainty" in cluster["keywords_json"]
    assert cluster["algorithm"] == "hashing-384-agglomerative-v1"
    assert cluster["paper_count"] == 1

    card = await client.put(
        f"{base}/papers/{paper.id}/reading-card",
        json={
            "mission_id": mission["id"],
            "summary": "An uncertainty-calibrated segmentation method.",
            "research_question": "How can weak supervision remain calibrated?",
            "method_flow": ["Train ensemble", "Apply calibration loss"],
            "reproducibility": ["Report seeds", "Retain calibration split"],
            "status": "reviewed",
        },
        headers=csrf_headers(client),
    )
    assert card.status_code == 200
    assert card.json()["status"] == "reviewed"

    monkeypatch.setattr("researchos.agents.service.dispatch_agent_run", lambda _run_id: None)
    generated = await client.post(
        f"{base}/papers/{paper.id}/reading-card/generate",
        json={"mission_id": mission["id"], "regenerate": True},
        headers=csrf_headers(client),
    )
    assert generated.status_code == 201
    await AgentRuntime(db_session, llm=MockLLMProvider()).run(
        uuid.UUID(generated.json()["agent_run_id"])
    )
    cards = await client.get(f"{base}/missions/{mission['id']}/reading-cards")
    assert cards.json()[0]["version"] == 2
    assert cards.json()[0]["status"] == "needs_review"
    assert cards.json()[0]["claims_json"][0]["evidence_status"] == "grounded"
    versions = await client.get(
        f"{base}/papers/{paper.id}/reading-card/versions",
        params={"mission_id": mission["id"]},
    )
    assert [item["source_type"] for item in versions.json()] == ["agent", "human"]

    note = await client.post(
        f"{base}/papers/{paper.id}/notes",
        json={
            "mission_id": mission["id"],
            "section_id": str(section.id),
            "quote": "estimates epistemic uncertainty",
            "content": "Compare ensemble cost against MC dropout.",
            "tags": ["method", "baseline"],
        },
        headers=csrf_headers(client),
    )
    assert note.status_code == 201
    notes = await client.get(
        f"{base}/papers/{paper.id}/notes", params={"mission_id": mission["id"]}
    )
    assert notes.json()[0]["section_id"] == str(section.id)


async def test_ensure_project_chunks_rebuilds_on_profile_mismatch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project, _, paper, _ = await _setup(client, db_session)
    project_id = uuid.UUID(project["id"])
    profile = get_active_profile()

    # First pass indexes the paper under the active profile.
    papers, chunks = await ensure_project_chunks(db_session, project_id)
    assert papers == 1 and chunks >= 1
    stored = list((await db_session.execute(select(PaperChunk))).scalars().all())
    assert stored
    assert all(chunk.embedding_model == profile.name for chunk in stored)
    assert all(len(chunk.embedding) == profile.dimensions for chunk in stored)
    original_ids = {chunk.id for chunk in stored}

    # Up-to-date chunks are left alone.
    assert await ensure_project_chunks(db_session, project_id) == (0, 0)

    # Simulate chunks built under a previous profile: they must be rebuilt.
    await db_session.execute(
        update(PaperChunk)
        .where(PaperChunk.paper_id == paper.id)
        .values(embedding_model="hashing-384-v1")
    )
    await db_session.commit()
    papers_again, _ = await ensure_project_chunks(db_session, project_id)
    assert papers_again == 1
    rebuilt = list((await db_session.execute(select(PaperChunk))).scalars().all())
    assert all(chunk.embedding_model == profile.name for chunk in rebuilt)
    assert original_ids.isdisjoint(chunk.id for chunk in rebuilt)


async def test_note_update_optimistic_lock(client: AsyncClient, db_session: AsyncSession) -> None:
    project, mission, paper, section = await _setup(client, db_session)
    base = f"/projects/{project['id']}"

    created = await client.post(
        f"{base}/papers/{paper.id}/notes",
        json={
            "mission_id": mission["id"],
            "section_id": str(section.id),
            "quote": "epistemic uncertainty",
            "content": "Initial note.",
            "tags": ["method"],
        },
        headers=csrf_headers(client),
    )
    assert created.status_code == 201
    note = created.json()
    assert note["version"] == 1

    updated = await client.patch(
        f"{base}/notes/{note['id']}",
        json={"expected_version": 1, "content": "Revised note.", "tags": ["method", "todo"]},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["content"] == "Revised note."

    # A stale expected_version must be rejected with a 409 conflict.
    conflict = await client.patch(
        f"{base}/notes/{note['id']}",
        json={"expected_version": 1, "content": "Stale write."},
        headers=csrf_headers(client),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "reading_note_version_conflict"

    # The rejected write must not have landed.
    notes = await client.get(f"{base}/papers/{paper.id}/notes")
    assert notes.json()[0]["content"] == "Revised note."
    assert notes.json()[0]["version"] == 2


async def test_note_delete_lifecycle(client: AsyncClient, db_session: AsyncSession) -> None:
    project, _, paper, _ = await _setup(client, db_session)
    base = f"/projects/{project['id']}"

    created = await client.post(
        f"{base}/papers/{paper.id}/notes",
        json={"quote": "calibration loss", "content": "To be deleted."},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201
    note_id = created.json()["id"]

    deleted = await client.delete(f"{base}/notes/{note_id}", headers=csrf_headers(client))
    assert deleted.status_code == 204

    notes = await client.get(f"{base}/papers/{paper.id}/notes")
    assert notes.json() == []

    # Deleting twice (or patching a gone note) is a 404.
    again = await client.delete(f"{base}/notes/{note_id}", headers=csrf_headers(client))
    assert again.status_code == 404
