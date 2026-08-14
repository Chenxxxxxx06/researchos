"""Pure checks for deterministic paper chunking and local vector embeddings."""

from __future__ import annotations

import re

from researchos.knowledge.embeddings import embed_texts, hashing_embedding
from researchos.knowledge.indexing import split_text
from researchos.knowledge.profiles import EmbeddingProfile

# Small budgets so tests stay compact: 15*4=60 chars target, 80 max, 20 overlap.
_TEST_PROFILE = EmbeddingProfile(
    name="test-hashing",
    provider="local-hashing",
    model="blake2b-feature-hashing",
    dimensions=1024,
    normalize=True,
    chunk_target_tokens=15,
    chunk_max_tokens=20,
    chunk_overlap_tokens=5,
    chars_per_token=4.0,
)


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _sentence(text: str, words: int, marker: str) -> str:
    return " ".join(f"{marker}{index}" for index in range(words)) + "."


def test_hashing_embedding_is_normalized_deterministic_and_discriminative() -> None:
    query = hashing_embedding("epistemic uncertainty calibration")
    related = hashing_embedding("calibrated epistemic uncertainty estimation")
    unrelated = hashing_embedding("database transaction isolation level")

    assert len(query) == 1024
    assert query == hashing_embedding("epistemic uncertainty calibration")
    assert abs(_cosine(query, query) - 1.0) < 1e-6
    assert _cosine(query, related) > _cosine(query, unrelated)


async def test_embed_texts_hashing_matches_profile_dimensions() -> None:
    vectors = await embed_texts(["alpha beta", "gamma"], _TEST_PROFILE)
    assert len(vectors) == 2
    assert all(len(vector) == _TEST_PROFILE.dimensions for vector in vectors)
    assert vectors[0] == hashing_embedding("alpha beta")


def test_split_text_aligns_to_sentence_boundaries_with_exact_offsets() -> None:
    sentences = [_sentence("Method", 6, f"s{i}w") for i in range(12)]
    text = " ".join(sentences)
    chunks = split_text(text, _TEST_PROFILE)

    assert len(chunks) > 2
    for start, end, content in chunks:
        # Exact offset round-trip into the source body.
        assert text[start:end] == content
        # Boundaries fall on sentence edges: no mid-sentence cut.
        assert content.endswith(".")
        assert not content.startswith(" ") and not content.endswith(" ")
    # Every sentence is covered by at least one chunk (no omissions).
    for sentence in sentences:
        assert any(sentence in content for _, _, content in chunks)


def test_split_text_overlap_repeats_whole_sentences() -> None:
    sentences = [_sentence("Approach", 3, f"s{i}w") for i in range(16)]
    text = " ".join(sentences)
    chunks = split_text(text, _TEST_PROFILE)

    assert len(chunks) > 2
    # Consecutive chunks overlap, and the overlap is a whole-sentence prefix of
    # the later chunk: the later chunk starts at a sentence that the earlier
    # chunk already contained.
    pairs = zip(chunks, chunks[1:], strict=False)
    for (prev_start, prev_end, _), (start, end, content) in pairs:
        assert prev_start < start < prev_end <= end
        first_sentence = content.split(". ", 1)[0] + "."
        assert prev_start <= text.index(first_sentence, prev_start) < prev_end


def test_split_text_hard_splits_overlong_sentence_on_word_boundaries() -> None:
    overlong = " ".join(f"w{index}" for index in range(120))  # one huge sentence
    text = f"Short lead. {overlong} Short tail."
    chunks = split_text(text, _TEST_PROFILE)

    max_chars = int(_TEST_PROFILE.chunk_max_tokens * _TEST_PROFILE.chars_per_token)
    assert len(chunks) >= 3
    for start, end, content in chunks:
        assert text[start:end] == content
        assert len(content) <= max_chars
        # No mid-word cuts: content neither starts nor ends inside a word.
        assert (start == 0 or text[start - 1] == " ") and (end == len(text) or text[end] in " .")
    # Full coverage of the overlong sentence.
    rebuilt = "".join(
        content for _, _, content in chunks if any(piece in content for piece in overlong.split())
    )
    for word in overlong.split():
        assert word in rebuilt


def test_split_text_handles_cjk_and_empty_input() -> None:
    assert split_text("   ", _TEST_PROFILE) == []
    text = "我们提出了一种方法。它在三个数据集上验证。结论很稳健。"
    chunks = split_text(text, _TEST_PROFILE)
    assert len(chunks) == 1
    start, end, content = chunks[0]
    assert text[start:end] == content == text


def test_split_text_respects_max_budget_and_breaks_at_newlines() -> None:
    text = "第一段没有句号只有换行\n第二段同样如此"
    chunks = split_text(text, _TEST_PROFILE)
    assert len(chunks) == 1
    start, end, content = chunks[0]
    assert text[start:end] == content
    # Newline boundaries act as sentence edges: a budget smaller than one
    # paragraph splits there instead of mid-paragraph.
    tight = EmbeddingProfile(
        name="tight",
        provider="local-hashing",
        model="m",
        dimensions=1024,
        normalize=True,
        chunk_target_tokens=3,
        chunk_max_tokens=4,
        chunk_overlap_tokens=1,
        chars_per_token=4.0,
    )
    tight_chunks = split_text(text, tight)
    assert tight_chunks[0][2] == "第一段没有句号只有换行"
    assert not any(re.search(r"\n", content) for _, _, content in tight_chunks)
