"""Hybrid ranking determinism tests (pure, no I/O)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from researchos.research.providers.base import PaperResult
from researchos.research.ranking import LibraryModel, cosine, rank_results, tokenize


def _pr(external_id: str, title: str, *, abstract: str | None = None, published=None):
    return PaperResult(
        source="arxiv",
        external_id=external_id,
        title=title,
        abstract=abstract,
        published_at=published,
        url=f"http://arxiv.org/abs/{external_id}",
    )


def test_tokenize_drops_stopwords_and_short_tokens() -> None:
    tokens = tokenize("The quick model of a Transformer is x")
    assert "the" not in tokens and "of" not in tokens and "is" not in tokens
    assert "x" not in tokens  # <2 chars
    assert tokens == tokenize("The quick model of a Transformer is x")  # deterministic


def test_library_model_and_cosine_determinism() -> None:
    docs = [
        "diffusion models for planning",
        "diffusion policies in robotics",
        "language models for coding",
    ]
    m1 = LibraryModel.build(docs)
    m2 = LibraryModel.build(docs)
    assert m1.idf == m2.idf
    assert m1.centroid == m2.centroid
    v = m1.vector("diffusion planning with robots")
    v2 = m1.vector("diffusion planning with robots")
    assert cosine(v, m1.centroid) == cosine(v2, m2.centroid)
    assert 0.0 <= cosine(v, m1.centroid) <= 1.0
    assert cosine({}, m1.centroid) == 0.0


def test_rank_results_scores_in_unit_interval_and_sorted() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    results = [
        _pr("1", "diffusion planning for robots", abstract="diffusion planning",
            published=now - timedelta(days=30)),
        _pr("2", "unrelated genomics pipelines", abstract="sequencing",
            published=now - timedelta(days=3000)),
        _pr("3", "diffusion models survey", abstract="diffusion",
            published=now - timedelta(days=200)),
    ]
    library = [
        "diffusion planning robot manipulation",
        "diffusion policies for control",
        "planning with learned world models",
    ]
    ranked = rank_results(results, library_docs=library, now=now)

    scores = [r.extra["score"] for r in ranked]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    components = ranked[0].extra["score_components"]
    assert set(components) == {"rrf", "affinity", "recency"}
    # The on-topic recent paper outranks the stale off-topic one.
    ids = [r.external_id for r in ranked]
    assert ids.index("1") < ids.index("2")


def test_cold_start_folds_affinity_into_rrf() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    results = [
        _pr("1", "first result", published=now - timedelta(days=10)),
        _pr("2", "second result", published=now - timedelta(days=10)),
    ]
    ranked = rank_results(results, library_docs=["only one doc"], now=now)
    # Affinity must contribute nothing: score == 0.8*rrf + 0.2*recency.
    for r in ranked:
        c = r.extra["score_components"]
        assert c["affinity"] == 0.0
        assert abs(r.extra["score"] - (0.8 * c["rrf"] + 0.2 * c["recency"])) < 1e-3
    # Provider order preserved on cold start (rank 0 has higher rrf).
    assert [r.external_id for r in ranked] == ["1", "2"]


def test_rank_results_none_published_gets_neutral_recency() -> None:
    ranked = rank_results(
        [_pr("1", "some paper title")], library_docs=[], now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert ranked[0].extra["score_components"]["recency"] == 0.35


def test_rank_results_uses_provenance_ranks_when_present() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    a = _pr("1", "alpha", published=now)
    a.extra["sources"] = [
        {"provider": "arxiv", "external_id": "1", "url": "u", "rank": 0},
        {"provider": "s2", "external_id": "x", "url": "u", "rank": 1},
    ]
    b = _pr("2", "beta", published=now)
    b.extra["sources"] = [{"provider": "openalex", "external_id": "2", "url": "u", "rank": 5}]
    ranked = rank_results([b, a], library_docs=[], now=now)
    # Two provider listings beat one deep-ranked listing regardless of input order.
    assert [r.external_id for r in ranked] == ["1", "2"]
