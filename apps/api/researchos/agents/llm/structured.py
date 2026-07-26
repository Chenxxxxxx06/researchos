"""Structured-output extraction helpers.

Pure functions, no I/O. The runtime uses them to turn a model's final text into
a validated JSON object — or to fail the run visibly (never a silent empty
success).
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\n(.*?)```", re.DOTALL)


class StructuredOutputError(Exception):
    """The LLM's final text could not be parsed into the required object."""


def _loads_object(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _balanced_object_scan(text: str) -> dict | None:
    """Find the first balanced ``{...}`` slice that parses as a JSON object."""

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parsed = _loads_object(text[start : i + 1])
                    if parsed is not None:
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None


def extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output text.

    Accepts a bare object, a single Markdown-fenced object, or an object
    embedded in surrounding prose. Raises :class:`StructuredOutputError` when
    no parseable object exists.
    """

    parsed = _loads_object(text)
    if parsed is not None:
        return parsed

    fence = _FENCE_RE.search(text)
    if fence:
        parsed = _loads_object(fence.group(1))
        if parsed is not None:
            return parsed

    parsed = _balanced_object_scan(text)
    if parsed is not None:
        return parsed

    raise StructuredOutputError(
        f"LLM did not return a parseable JSON object: {text[:200]!r}"
    )


def _check_required(parsed: dict, schema: dict) -> None:
    """Raise when top-level ``required`` keys of ``schema`` are missing."""

    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [key for key in required if key not in parsed]
    if missing:
        raise StructuredOutputError(f"missing required keys: {', '.join(missing)}")
