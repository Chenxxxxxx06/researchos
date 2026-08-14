"""Real DashScope (text-embedding-v4) online tests — no mocking.

Run explicitly with:

    RUN_ONLINE_TESTS=1 uv run pytest tests/online -q

The module skips entirely unless ``RUN_ONLINE_TESTS=1`` is set and a
DashScope API key is available (env or apps/api/.env). The qwen profile is
used explicitly here; the global ``EMBEDDING_PROFILE`` setting (forced to the
hashing profile by conftest) is irrelevant for these tests.

Cost control: the whole module spends a handful of API calls over <20 short
texts — well under a few thousand tokens per run.
"""

from __future__ import annotations

import os

import pytest

from researchos.common.config import get_settings
from researchos.knowledge.profiles import _PROFILES

if os.environ.get("RUN_ONLINE_TESTS") != "1":
    pytest.skip("online tests disabled (set RUN_ONLINE_TESTS=1)", allow_module_level=True)
if not get_settings().dashscope_api_key:
    pytest.skip("DASHSCOPE_API_KEY not configured", allow_module_level=True)

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from researchos.knowledge.embeddings import embed_texts  # noqa: E402
from researchos.research.enums import PaperSectionKind  # noqa: E402
from tests.test_rag_search import _add_paper, _project, _search  # noqa: E402

_QWEN = _PROFILES["qwen-text-embedding-v4-1024"]

_ATTENTION_PASSAGE = (
    "Multi-head attention allows the model to jointly attend to information "
    "from different representation subspaces at different positions."
)
_UNRELATED_PASSAGE = (
    "To make pancakes, whisk flour, sugar, baking powder and milk, then cook "
    "the batter on a hot griddle until golden brown on both sides."
)
_QUERY = "attention mechanism for sequence modeling"


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


async def test_online_embed_dimensions_and_determinism() -> None:
    first = (await embed_texts([_QUERY], _QWEN))[0]
    second = (await embed_texts([_QUERY], _QWEN))[0]

    assert len(first) == 1024
    assert _cosine(first, second) > 0.999  # API is deterministic

    other = (await embed_texts([_UNRELATED_PASSAGE], _QWEN))[0]
    assert _cosine(first, other) < 0.9


async def test_online_semantic_discrimination() -> None:
    query_vec, related_vec, unrelated_vec = await embed_texts(
        [_QUERY, _ATTENTION_PASSAGE, _UNRELATED_PASSAGE], _QWEN
    )

    related = _cosine(query_vec, related_vec)
    unrelated = _cosine(query_vec, unrelated_vec)
    print(f"\nrelated={related:.4f} unrelated={unrelated:.4f} margin={related - unrelated:.4f}")
    assert related > unrelated + 0.1  # clear semantic separation


async def test_online_batch_boundary() -> None:
    texts = [f"short sample text number {index}" for index in range(11)]
    vectors = await embed_texts(texts, _QWEN)  # 10 + 1 split inside the adapter

    assert len(vectors) == 11
    assert all(len(vector) == 1024 for vector in vectors)


async def test_online_rag_search_quality(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: qwen-indexed chunks, paraphrased query hits the method section."""

    monkeypatch.setattr(get_settings(), "embedding_profile", _QWEN.name)
    email = "online-rag@example.com"
    project_id = await _project(client, email)
    await _add_paper(
        db_session,
        project_id,
        email,
        "Attention Is All You Need",
        [
            (PaperSectionKind.METHOD, "Model Architecture", _ATTENTION_PASSAGE),
            (
                PaperSectionKind.RESULTS,
                "Results",
                "The big transformer achieves 28.4 BLEU on English-to-German translation.",
            ),
        ],
    )
    await _add_paper(
        db_session,
        project_id,
        email,
        "Weeknight Pancakes",
        [(PaperSectionKind.METHOD, "Method", _UNRELATED_PASSAGE)],
    )

    # Paraphrase: none of the passage's key terms appear verbatim in the query.
    body = await _search(
        client, project_id, {"query": "jointly attending to multiple representation subspaces"}
    )
    assert body["embedding_model"] == _QWEN.name
    top = body["hits"][0]
    assert top["title"] == "Attention Is All You Need"
    assert top["kind"] == "method"
