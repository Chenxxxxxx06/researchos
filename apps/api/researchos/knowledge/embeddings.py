"""Embedding adapters: one async interface over local hashing and DashScope.

``embed_texts`` dispatches on ``profile.provider`` so indexing and querying
always produce vectors in the active profile's space. The local hashing
adapter is deterministic and dependency-free (offline/CI fallback); the
DashScope adapter calls Aliyun Bailian's OpenAI-compatible endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections import Counter

import httpx

from researchos.common.config import get_settings

from .profiles import EmbeddingProfile

_WORD_RE = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*|[\u4e00-\u9fff]+")

# DashScope text-embedding-v4 accepts at most 10 inputs per request.
_DASHSCOPE_BATCH_SIZE = 10
_DASHSCOPE_MAX_ATTEMPTS = 3
_DASHSCOPE_TIMEOUT_SECONDS = 60.0
# Statuses worth retrying (rate limiting and server-side faults).
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot produce valid vectors."""


def embedding_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", raw):
            if len(raw) == 1:
                tokens.append(raw)
            else:
                tokens.extend(raw[index : index + 2] for index in range(len(raw) - 1))
        elif len(raw) >= 2:
            tokens.append(raw)
    return tokens


def hashing_embedding(text: str, *, dimensions: int = 1024) -> list[float]:
    """Feature-hashing vector with signed buckets and L2 normalization."""

    counts = Counter(embedding_tokens(text))
    vector = [0.0] * dimensions
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


async def embed_texts(texts: list[str], profile: EmbeddingProfile) -> list[list[float]]:
    """Embed ``texts`` in the space defined by ``profile``."""

    if profile.provider == "local-hashing":
        return [
            _validate(hashing_embedding(text, dimensions=profile.dimensions), profile)
            for text in texts
        ]
    if profile.provider == "dashscope":
        return await _embed_dashscope(texts, profile)
    raise EmbeddingError(
        f"Unknown embedding provider {profile.provider!r} (profile {profile.name})."
    )


def _validate(vector: list[float], profile: EmbeddingProfile) -> list[float]:
    if len(vector) != profile.dimensions:
        raise EmbeddingError(
            f"Provider returned a {len(vector)}-dim vector; profile {profile.name} "
            f"requires {profile.dimensions}."
        )
    return vector


async def _embed_dashscope(texts: list[str], profile: EmbeddingProfile) -> list[list[float]]:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise EmbeddingError(
            f"Profile {profile.name} needs a DashScope API key; set the "
            "DASHSCOPE_API_KEY environment variable (never commit it)."
        )
    # The key is only ever placed in the Authorization header; it is never
    # logged or included in error messages.
    headers = {"Authorization": f"Bearer {settings.dashscope_api_key}"}
    url = f"{settings.dashscope_base_url.rstrip('/')}/embeddings"
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=_DASHSCOPE_TIMEOUT_SECONDS) as client:
        for offset in range(0, len(texts), _DASHSCOPE_BATCH_SIZE):
            batch = texts[offset : offset + _DASHSCOPE_BATCH_SIZE]
            payload = {"model": profile.model, "input": batch, "dimensions": profile.dimensions}
            data = await _post_with_retry(client, url, payload, headers)
            items = sorted(data, key=lambda item: item["index"])
            if len(items) != len(batch):
                raise EmbeddingError(
                    f"DashScope returned {len(items)} embeddings for a batch of {len(batch)}."
                )
            vectors.extend(_validate(list(item["embedding"]), profile) for item in items)
    return vectors


async def _post_with_retry(
    client: httpx.AsyncClient, url: str, payload: dict, headers: dict[str, str]
) -> list[dict]:
    last_error: Exception | None = None
    for attempt in range(_DASHSCOPE_MAX_ATTEMPTS):
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in _RETRYABLE_STATUSES:
                raise EmbeddingError(f"DashScope HTTP {response.status_code} (retryable).")
            response.raise_for_status()
            body = response.json()
            data = body.get("data")
            if not isinstance(data, list):
                raise EmbeddingError("DashScope response has no 'data' list.")
            return data
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(f"DashScope HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, EmbeddingError) as exc:
            last_error = exc
            if attempt < _DASHSCOPE_MAX_ATTEMPTS - 1:
                await asyncio.sleep(0.5 * 2**attempt)
    raise EmbeddingError(
        f"DashScope embedding request failed after {_DASHSCOPE_MAX_ATTEMPTS} attempts."
    ) from last_error
