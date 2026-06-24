"""Citation integrity: only papers actually retrieved or in the library may be
cited. Everything else is dropped (no fabricated citations)."""

from __future__ import annotations


def filter_citations(candidate_keys: list[str], whitelist: set[str]) -> tuple[list[str], list[str]]:
    """Split candidate citation keys into (kept, dropped).

    A key has the form ``"<source>:<external_id>"``. ``kept`` preserves order and
    de-duplicates; ``dropped`` are keys with no backing source.
    """

    kept: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for key in candidate_keys:
        if key in whitelist:
            if key not in seen:
                seen.add(key)
                kept.append(key)
        else:
            dropped.append(key)
    return kept, dropped
