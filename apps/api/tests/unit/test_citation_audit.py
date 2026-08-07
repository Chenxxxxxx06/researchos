"""Pure duplicate and metadata checks for the citation organizer."""

from __future__ import annotations

import uuid

from researchos.citations.service import build_citation_audit
from researchos.research.models import Paper


def _paper(title: str, *, doi: str | None, authors: list[str]) -> Paper:
    return Paper(
        project_id=uuid.uuid4(),
        source="semantic_scholar",
        external_id=str(uuid.uuid4()),
        title=title,
        abstract="A",
        authors_json=authors,
        venue=None,
        url="https://example.test/paper",
        doi=doi,
        metadata_json={},
        imported_by=uuid.uuid4(),
    )


def test_citation_audit_finds_doi_duplicates_and_missing_fields() -> None:
    first = _paper("A careful study", doi="10.1000/ABC", authors=["Ada Lovelace"])
    second = _paper(
        "A careful study (publisher copy)",
        doi="https://doi.org/10.1000/abc",
        authors=[],
    )

    items, duplicates, missing_count, bibtex = build_citation_audit([first, second])

    assert len(items) == 2
    assert duplicates[0]["count"] == 2
    assert "authors" in items[1]["missing_fields"]
    assert missing_count > 0
    assert bibtex.count("@article") == 2
