"""Pure unit tests for the line-level three-way merge (documents/merge.py)."""

from __future__ import annotations

from researchos.documents.merge import three_way_merge

_BASE = "line1\nline2\nline3\n"


def test_identical_edits_merge_once() -> None:
    edited = "line1\nCHANGED\nline3\n"
    result = three_way_merge(_BASE, edited, edited)
    assert result.clean is True
    assert result.conflicts == []
    assert result.merged == edited
    assert result.merged is not None
    assert result.merged.count("CHANGED") == 1


def test_disjoint_edits_merge_clean() -> None:
    server = "SERVER1\nline2\nline3\n"
    client = "line1\nline2\nCLIENT3\n"
    result = three_way_merge(_BASE, server, client)
    assert result.clean is True
    assert result.merged == "SERVER1\nline2\nCLIENT3\n"


def test_overlapping_edits_conflict() -> None:
    server = "line1\nSERVER\nline3\n"
    client = "line1\nCLIENT\nline3\n"
    result = three_way_merge(_BASE, server, client)
    assert result.clean is False
    assert result.merged is None
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.base_start == 1
    assert conflict.base_end == 2
    assert conflict.base_text == "line2\n"
    assert conflict.server_text == "SERVER\n"
    assert conflict.client_text == "CLIENT\n"
    payload = conflict.to_payload()
    assert set(payload) == {"base_start", "base_end", "base_text", "server_text", "client_text"}


def test_one_side_only_change_takes_that_side() -> None:
    server = "line1\nSERVER\nline3\nextra\n"
    result = three_way_merge(_BASE, server, _BASE)
    assert result.clean is True
    assert result.merged == server


def test_base_equals_server_takes_client() -> None:
    client = "intro\nline1\nline2\nline3\n"
    result = three_way_merge(_BASE, _BASE, client)
    assert result.clean is True
    assert result.merged == client


def test_empty_base_identical_additions() -> None:
    result = three_way_merge("", "new\n", "new\n")
    assert result.clean is True
    assert result.merged == "new\n"


def test_empty_base_diverging_additions_conflict() -> None:
    result = three_way_merge("", "server\n", "client\n")
    assert result.clean is False
    assert result.merged is None
    assert len(result.conflicts) == 1
    assert result.conflicts[0].base_text == ""


def test_insertion_next_to_change_is_ordered() -> None:
    # Server inserts before line2; client rewrites line2 — no data loss.
    server = "line1\ninserted\nline2\nline3\n"
    client = "line1\nCLIENT\nline3\n"
    result = three_way_merge(_BASE, server, client)
    assert result.clean is True
    assert result.merged is not None
    assert "inserted\n" in result.merged
    assert "CLIENT\n" in result.merged


def test_merge_payload_shape() -> None:
    result = three_way_merge(_BASE, _BASE, _BASE)
    payload = result.to_payload()
    assert payload == {"clean": True, "merged_content": _BASE, "conflicts": []}
