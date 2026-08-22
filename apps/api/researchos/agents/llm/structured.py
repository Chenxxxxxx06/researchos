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

    raise StructuredOutputError(f"LLM did not return a parseable JSON object: {text[:200]!r}")


def _check_required(parsed: dict, schema: dict) -> None:
    """Validate the supported JSON-Schema subset recursively.

    Agent schemas use objects, arrays, primitive types, enums, required keys,
    and numeric/string/array bounds. Enforcing them here prevents a top-level
    shell with malformed nested artifacts from reaching finalize side effects.
    """

    errors: list[str] = []
    _validate_value(parsed, schema, path="$", errors=errors)
    if errors:
        raise StructuredOutputError("; ".join(errors[:20]))


def _validate_value(value: object, schema: object, *, path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        return
    declared = schema.get("type")
    allowed_types = declared if isinstance(declared, list) else [declared] if declared else []
    if allowed_types and not any(_matches_type(value, item) for item in allowed_types):
        errors.append(f"{path}: expected {'|'.join(str(item) for item in allowed_types)}")
        return
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{path}: value is outside enum")
        return
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required key {key}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value:
                    _validate_value(value[key], child_schema, path=f"{path}.{key}", errors=errors)
    elif isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: requires at least {minimum} items")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: accepts at most {maximum} items")
        item_schema = schema.get("items")
        for index, item in enumerate(value):
            _validate_value(item, item_schema, path=f"{path}[{index}]", errors=errors)
    elif isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: string is shorter than {minimum}")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: string is longer than {maximum}")
    elif isinstance(value, int | float) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int | float) and value < minimum:
            errors.append(f"{path}: number is below {minimum}")
        if isinstance(maximum, int | float) and value > maximum:
            errors.append(f"{path}: number is above {maximum}")


def _matches_type(value: object, declared: object) -> bool:
    if declared == "null":
        return value is None
    if declared == "object":
        return isinstance(value, dict)
    if declared == "array":
        return isinstance(value, list)
    if declared == "string":
        return isinstance(value, str)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return True
