"""Pure SEARCH/REPLACE resolution and hunk-derivation tests (no DB, no FS)."""

from __future__ import annotations

import pytest

from researchos.patches.resolution import (
    EditBlock,
    EditResolutionError,
    compute_hunks,
    resolve_edits,
)

BASE = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"


def test_exact_single_occurrence_replaced() -> None:
    out = resolve_edits(
        BASE,
        [EditBlock(search="    return a + b\n", replace="    return b + a\n")],
    )
    assert "return b + a" in out
    assert "return a - b" in out  # untouched


def test_exact_multiple_occurrences_ambiguous() -> None:
    base = "x = 1\nx = 1\n"
    with pytest.raises(EditResolutionError) as exc:
        resolve_edits(base, [EditBlock(search="x = 1\n", replace="x = 2\n")])
    assert exc.value.failures[0].reason == "ambiguous"


def test_not_found() -> None:
    with pytest.raises(EditResolutionError) as exc:
        resolve_edits(BASE, [EditBlock(search="does not exist", replace="nope")])
    assert exc.value.failures[0].reason == "not_found"


def test_empty_search_rejected() -> None:
    with pytest.raises(EditResolutionError) as exc:
        resolve_edits(BASE, [EditBlock(search="", replace="x")])
    assert exc.value.failures[0].reason == "empty_search"


def test_whitespace_fuzzy_match_with_indent_shift() -> None:
    base = "class A:\n    def f(self):\n        return 1\n"
    # Search uses different (smaller) indentation; fuzzy match must find the
    # window and re-indent the replacement to the file's actual indent.
    out = resolve_edits(
        base,
        [EditBlock(search="def f(self):\n    return 1\n", replace="def f(self):\n    return 2\n")],
    )
    assert "    def f(self):" in out
    assert "        return 2" in out


def test_fuzzy_requires_unique_window() -> None:
    base = "if x:\n    go()\nif x:\n    go()\n"
    with pytest.raises(EditResolutionError) as exc:
        resolve_edits(base, [EditBlock(search="if x:\n  go()\n", replace="stop()\n")])
    assert exc.value.failures[0].reason == "ambiguous"


def test_sequential_edits_apply_to_evolving_text() -> None:
    base = "a\nb\nc\n"
    out = resolve_edits(
        base,
        [
            EditBlock(search="b\n", replace="B\nB2\n"),
            # Only resolvable after the first edit ran.
            EditBlock(search="B2\nc\n", replace="B2\nC\n"),
        ],
    )
    assert out == "a\nB\nB2\nC\n"


def test_failures_aggregate_across_blocks() -> None:
    with pytest.raises(EditResolutionError) as exc:
        resolve_edits(
            BASE,
            [
                EditBlock(search="", replace=""),
                EditBlock(search="missing text", replace="x"),
                EditBlock(search="    return a + b\n", replace="    return b + a\n"),
            ],
        )
    reasons = {(f.index, f.reason) for f in exc.value.failures}
    assert reasons == {(0, "empty_search"), (1, "not_found")}


def test_compute_hunks_headers_and_offsets() -> None:
    base = "\n".join(f"line{i}" for i in range(1, 21)) + "\n"
    new = base.replace("line10", "LINE10")
    hunks = compute_hunks(base, new)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.header.startswith("@@ -7,7 +7,7 @@")
    assert h.old_start == 7 and h.new_start == 7
    assert "-line10" in h.content and "+LINE10" in h.content


def test_compute_hunks_empty_for_identical() -> None:
    assert compute_hunks(BASE, BASE) == []


def test_resolve_then_hunks_round_trip() -> None:
    new = resolve_edits(
        BASE, [EditBlock(search="    return a - b\n", replace="    return a - b - 1\n")]
    )
    hunks = compute_hunks(BASE, new)
    assert len(hunks) == 1
    assert "+    return a - b - 1" in hunks[0].content
