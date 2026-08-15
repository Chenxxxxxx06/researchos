"""Embedding profiles: the single source of truth for index-legality.

A profile pins the embedding model, vector dimensionality, normalization and
chunking budget. Indexing and querying must always read their parameters from
the *same* profile object; chunks record ``profile.name`` so a profile change
is detectable and triggers a full rebuild (see ``ensure_project_chunks``).
"""

from __future__ import annotations

from dataclasses import dataclass

from researchos.common.config import get_settings


@dataclass(frozen=True)
class EmbeddingProfile:
    name: str
    provider: str  # "local-hashing" | "dashscope"
    model: str
    dimensions: int
    normalize: bool
    # Chunking budget in approximate tokens. We deliberately avoid a tokenizer
    # dependency and approximate tokens with characters: English scientific
    # prose averages ~4 characters per token (the commonly cited rule of
    # thumb), which is accurate enough for retrieval-sized chunk packing.
    chunk_target_tokens: int = 600
    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 100
    chars_per_token: float = 4.0


_PROFILES: dict[str, EmbeddingProfile] = {
    # Offline/CI fallback: deterministic blake2b feature hashing, no network.
    "hashing-1024-v2": EmbeddingProfile(
        name="hashing-1024-v2",
        provider="local-hashing",
        model="blake2b-feature-hashing",
        dimensions=1024,
        normalize=True,
    ),
    # Aliyun Bailian online API (OpenAI-compatible /embeddings endpoint).
    "qwen-text-embedding-v4-1024": EmbeddingProfile(
        name="qwen-text-embedding-v4-1024",
        provider="dashscope",
        model="text-embedding-v4",
        dimensions=1024,
        normalize=True,
    ),
}


def get_active_profile() -> EmbeddingProfile:
    """Return the profile selected by the ``embedding_profile`` setting."""

    name = get_settings().embedding_profile
    try:
        return _PROFILES[name]
    except KeyError:
        known = ", ".join(sorted(_PROFILES))
        raise ValueError(
            f"Unknown embedding profile {name!r}; registered profiles: {known}"
        ) from None
