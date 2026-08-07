"""Pure checks for deterministic paper chunking and local vector embeddings."""

from __future__ import annotations

from researchos.knowledge.indexing import hashing_embedding, split_text


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_hashing_embedding_is_normalized_deterministic_and_discriminative() -> None:
    query = hashing_embedding("epistemic uncertainty calibration")
    related = hashing_embedding("calibrated epistemic uncertainty estimation")
    unrelated = hashing_embedding("database transaction isolation level")

    assert len(query) == 384
    assert query == hashing_embedding("epistemic uncertainty calibration")
    assert abs(_cosine(query, query) - 1.0) < 1e-6
    assert _cosine(query, related) > _cosine(query, unrelated)


def test_split_text_keeps_offsets_and_overlap() -> None:
    text = " ".join(f"token-{index}" for index in range(600))
    chunks = split_text(text, size=240, overlap=40)

    assert len(chunks) > 2
    for start, end, content in chunks:
        assert text[start:end] == content
        assert len(content) <= 240
    assert chunks[1][0] < chunks[0][1]
