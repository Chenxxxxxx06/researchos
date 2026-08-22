"""Hybrid search ranking: RRF provider relevance + library affinity + recency.

Pure and deterministic — no I/O, no randomness. The library model is a
hand-rolled TF-IDF centroid built per request from at most a few hundred
short documents.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from researchos.research.providers.base import PaperResult
from researchos.research.providers.federated import RRF_K, normalize_title

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "more",
        "most",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "over",
        "such",
        "than",
        "that",
        "the",
        "their",
        "these",
        "this",
        "those",
        "to",
        "under",
        "use",
        "used",
        "using",
        "via",
        "was",
        "we",
        "were",
        "which",
        "with",
        "within",
    }
)

# Half-life-style recency decay constant (days).
_RECENCY_TAU_DAYS = 730.0
_NEUTRAL_RECENCY = 0.35
# Affinity needs a minimally informative library.
MIN_LIBRARY_DOCS = 3


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _l2_normalize(vector: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(v * v for v in vector.values()))
    if norm == 0.0:
        return {}
    return {k: v / norm for k, v in vector.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(b) < len(a):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass
class LibraryModel:
    idf: dict[str, float]
    centroid: dict[str, float]
    doc_count: int

    @classmethod
    def build(cls, docs: list[str], *, weights: list[float] | None = None) -> LibraryModel:
        token_lists = [tokenize(doc) for doc in docs]
        n = len(token_lists)
        if weights is None or len(weights) != n:
            weights = [1.0] * n
        weights = [max(0.0, float(weight)) for weight in weights]
        df: dict[str, int] = {}
        for tokens in token_lists:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        idf = {t: math.log((n + 1) / (count + 1)) + 1.0 for t, count in df.items()}

        centroid: dict[str, float] = {}
        total_weight = sum(weights)
        for tokens, document_weight in zip(token_lists, weights, strict=True):
            vector = _vectorize(tokens, idf)
            for term, value in vector.items():
                centroid[term] = centroid.get(term, 0.0) + value * document_weight
        if total_weight:
            centroid = {term: value / total_weight for term, value in centroid.items()}
        return cls(idf=idf, centroid=centroid, doc_count=n)

    def vector(self, text: str) -> dict[str, float]:
        return _vectorize(tokenize(text), self.idf)


def _vectorize(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf: dict[str, int] = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
    vector = {t: count * idf.get(t, 1.0) for t, count in tf.items()}
    return _l2_normalize(vector)


def _recency(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return _NEUTRAL_RECENCY
    age_days = max(0.0, (now - published_at).total_seconds() / 86_400.0)
    return math.exp(-age_days / _RECENCY_TAU_DAYS)


def _rrf_raw(result: PaperResult, index: int) -> float:
    sources = result.extra.get("sources")
    if isinstance(sources, list) and sources:
        return sum(1.0 / (RRF_K + int(s.get("rank", 0))) for s in sources if isinstance(s, dict))
    # Single-provider search: provenance is the list position itself.
    return 1.0 / (RRF_K + index)


def rank_results(
    results: list[PaperResult],
    *,
    library_docs: list[str],
    library_weights: list[float] | None = None,
    now: datetime | None = None,
) -> list[PaperResult]:
    """Score and reorder results in place-order; annotates ``extra``."""

    if not results:
        return []
    now = now or datetime.now(tz=UTC)

    model: LibraryModel | None = None
    if len(library_docs) >= MIN_LIBRARY_DOCS:
        model = LibraryModel.build(library_docs, weights=library_weights)
    # Cold start: fold the affinity weight into RRF so ordering tracks
    # provider order.
    w_rrf, w_aff, w_rec = (0.5, 0.3, 0.2) if model is not None else (0.8, 0.0, 0.2)

    raw_rrf = [_rrf_raw(result, i) for i, result in enumerate(results)]
    lo, hi = min(raw_rrf), max(raw_rrf)
    span = hi - lo

    scored: list[tuple[float, PaperResult]] = []
    for i, result in enumerate(results):
        rrf = 1.0 if span == 0.0 else (raw_rrf[i] - lo) / span
        affinity = 0.0
        if model is not None:
            doc = f"{result.title} {result.abstract or ''}"
            affinity = cosine(model.vector(doc), model.centroid)
        recency = _recency(result.published_at, now)
        score = w_rrf * rrf + w_aff * affinity + w_rec * recency
        result.extra["score"] = round(score, 4)
        result.extra["score_components"] = {
            "rrf": round(rrf, 4),
            "affinity": round(affinity, 4),
            "recency": round(recency, 4),
        }
        scored.append((score, result))

    scored.sort(key=lambda item: (-item[0], normalize_title(item[1].title)))
    return [result for _, result in scored]
