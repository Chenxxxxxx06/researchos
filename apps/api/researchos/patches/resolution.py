"""SEARCH/REPLACE edit resolution and unified-diff hunk derivation.

Pure functions (no DB, no filesystem): the patch service resolves agent-proposed
edit blocks against a snapshotted base text and materializes the new content;
hunks are server-derived for review display. Fully unit-testable.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

EditFailureReason = Literal["empty_search", "not_found", "ambiguous"]

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class EditBlock:
    search: str
    replace: str


@dataclass(frozen=True)
class EditFailure:
    index: int
    reason: EditFailureReason


@dataclass(frozen=True)
class HunkData:
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str


class EditResolutionError(Exception):
    """One or more edit blocks failed to resolve against the base text."""

    def __init__(self, failures: list[EditFailure]) -> None:
        self.failures = failures
        summary = "; ".join(f"edit {f.index}: {f.reason}" for f in failures)
        super().__init__(f"Edit resolution failed: {summary}")


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _shift_indent(line: str, delta: int) -> str:
    if not line.strip():
        return line
    if delta > 0:
        return " " * delta + line
    if delta < 0:
        indent = _indent(line)
        drop = min(-delta, len(indent))
        return line[drop:]
    return line


def _fuzzy_apply(text: str, block: EditBlock) -> tuple[str | None, EditFailureReason | None]:
    """Whitespace-fuzzy line-window match with indent-shift reconstruction.

    Requires exactly one window of lines whose stripped forms equal the search
    lines' stripped forms. Rejoins with ``\n`` (normalizes CRLF in the fuzzy
    path only; the exact-match path preserves the text byte-for-byte).
    Returns ``(new_text, None)`` on success or ``(None, reason)`` on failure.
    """

    search_lines = block.search.splitlines()
    if not search_lines:
        return None, "not_found"
    text_lines = text.splitlines()
    width = len(search_lines)
    stripped_search = [ln.strip() for ln in search_lines]

    starts = [
        s
        for s in range(len(text_lines) - width + 1)
        if all(text_lines[s + j].strip() == stripped_search[j] for j in range(width))
    ]
    if not starts:
        return None, "not_found"
    if len(starts) > 1:
        return None, "ambiguous"

    start = starts[0]
    delta = len(_indent(text_lines[start])) - len(_indent(search_lines[0]))
    replace_lines = [_shift_indent(ln, delta) for ln in block.replace.splitlines()]

    new_lines = text_lines[:start] + replace_lines + text_lines[start + width :]
    result = "\n".join(new_lines)
    if text.endswith("\n"):
        result += "\n"
    return result, None


def resolve_edits(base: str, edits: list[EditBlock]) -> str:
    """Apply SEARCH/REPLACE blocks sequentially to the evolving text.

    Failures are collected across all blocks (resolution continues on the
    text-so-far so the caller gets the complete failure list) and raised
    together as ``EditResolutionError``.
    """

    text = base
    failures: list[EditFailure] = []
    for index, block in enumerate(edits):
        if block.search == "":
            failures.append(EditFailure(index=index, reason="empty_search"))
            continue
        count = text.count(block.search)
        if count == 1:
            text = text.replace(block.search, block.replace, 1)
            continue
        if count > 1:
            failures.append(EditFailure(index=index, reason="ambiguous"))
            continue
        resolved, reason = _fuzzy_apply(text, block)
        if resolved is not None:
            text = resolved
        else:
            failures.append(EditFailure(index=index, reason=reason or "not_found"))
    if failures:
        raise EditResolutionError(failures)
    return text


def compute_hunks(base: str, new: str, n: int = 3) -> list[HunkData]:
    """Derive display hunks from a real ``difflib.unified_diff`` run."""

    base_lines = base.splitlines()
    new_lines = new.splitlines()
    hunks: list[HunkData] = []
    header = ""
    old_start = old_count = new_start = new_count = 0
    body: list[str] = []

    def _flush() -> None:
        if header:
            hunks.append(
                HunkData(
                    header=header,
                    old_start=old_start,
                    old_lines=old_count,
                    new_start=new_start,
                    new_lines=new_count,
                    content="\n".join(body),
                )
            )

    for line in difflib.unified_diff(base_lines, new_lines, n=n, lineterm=""):
        if line.startswith(("---", "+++")):
            continue
        match = _HUNK_HEADER_RE.match(line)
        if match:
            _flush()
            header = line
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            body = []
        else:
            body.append(line)
    _flush()
    return hunks
