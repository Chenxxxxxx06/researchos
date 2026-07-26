"""Minimal line-level three-way merge (diff3) used for CAS save-conflict hints.

Pure, deterministic, stdlib-only. The server never writes merged content; the
result is returned to the client inside the 409 ``document_version_conflict``
details so the editor can merge instead of losing work.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class MergeConflict:
    base_start: int
    base_end: int
    base_text: str
    server_text: str
    client_text: str

    def to_payload(self) -> dict:
        return {
            "base_start": self.base_start,
            "base_end": self.base_end,
            "base_text": self.base_text,
            "server_text": self.server_text,
            "client_text": self.client_text,
        }


@dataclass
class MergeResult:
    merged: str | None
    clean: bool
    conflicts: list[MergeConflict]

    def to_payload(self) -> dict:
        return {
            "clean": self.clean,
            "merged_content": self.merged,
            "conflicts": [c.to_payload() for c in self.conflicts],
        }


@dataclass(frozen=True)
class _Block:
    """A contiguous region of base lines replaced by ``replacement`` on one side."""

    base_start: int
    base_end: int
    replacement: tuple[str, ...]


def _change_blocks(base: list[str], other: list[str]) -> list[_Block]:
    matcher = SequenceMatcher(a=base, b=other, autojunk=False)
    blocks: list[_Block] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        blocks.append(_Block(i1, i2, tuple(other[j1:j2])))
    return blocks


def _overlaps(a: _Block, b: _Block) -> bool:
    if a.base_start == b.base_start and a.base_end == b.base_end:
        # Same region — including two inserts at the same point.
        return True
    return a.base_start < b.base_end and b.base_start < a.base_end


def _side_text(base: list[str], blocks: list[_Block], start: int, end: int) -> str:
    """Render base[start:end] with a side's (sorted, disjoint) blocks applied."""

    parts: list[str] = []
    cursor = start
    for block in blocks:
        parts.extend(base[cursor : block.base_start])
        parts.extend(block.replacement)
        cursor = block.base_end
    parts.extend(base[cursor:end])
    return "".join(parts)


def three_way_merge(base: str, server: str, client: str) -> MergeResult:
    """Merge two descendants of ``base``.

    A base region changed by only one side takes that side's text; identical
    changes are taken once; different overlapping changes become conflicts.
    ``merged`` is assembled only when there are no conflicts.
    """

    base_lines = base.splitlines(keepends=True)
    server_blocks = _change_blocks(base_lines, server.splitlines(keepends=True))
    client_blocks = _change_blocks(base_lines, client.splitlines(keepends=True))

    parts: list[str] = []
    conflicts: list[MergeConflict] = []
    cursor = 0
    si = ci = 0

    while si < len(server_blocks) or ci < len(client_blocks):
        sb = server_blocks[si] if si < len(server_blocks) else None
        cb = client_blocks[ci] if ci < len(client_blocks) else None

        if sb is not None and cb is not None and _overlaps(sb, cb):
            # Expand to the full transitive overlap cluster on both sides.
            region_start = min(sb.base_start, cb.base_start)
            region_end = max(sb.base_end, cb.base_end)
            s_end, c_end = si + 1, ci + 1
            changed = True
            while changed:
                changed = False
                while s_end < len(server_blocks) and (
                    server_blocks[s_end].base_start < region_end
                ):
                    region_end = max(region_end, server_blocks[s_end].base_end)
                    s_end += 1
                    changed = True
                while c_end < len(client_blocks) and (
                    client_blocks[c_end].base_start < region_end
                ):
                    region_end = max(region_end, client_blocks[c_end].base_end)
                    c_end += 1
                    changed = True

            parts.extend(base_lines[cursor:region_start])
            server_text = _side_text(
                base_lines, server_blocks[si:s_end], region_start, region_end
            )
            client_text = _side_text(
                base_lines, client_blocks[ci:c_end], region_start, region_end
            )
            if server_text == client_text:
                parts.append(server_text)
            else:
                conflicts.append(
                    MergeConflict(
                        base_start=region_start,
                        base_end=region_end,
                        base_text="".join(base_lines[region_start:region_end]),
                        server_text=server_text,
                        client_text=client_text,
                    )
                )
            cursor = region_end
            si, ci = s_end, c_end
            continue

        # Pick the next non-overlapping block; on a start tie, apply the pure
        # insertion first so it lands before the other side's changed region.
        if cb is None:
            block, si = sb, si + 1
        elif sb is None:
            block, ci = cb, ci + 1
        elif sb.base_start < cb.base_start:
            block, si = sb, si + 1
        elif cb.base_start < sb.base_start:
            block, ci = cb, ci + 1
        elif sb.base_start == sb.base_end:
            block, si = sb, si + 1
        else:
            block, ci = cb, ci + 1

        assert block is not None
        parts.extend(base_lines[cursor : block.base_start])
        parts.extend(block.replacement)
        cursor = max(cursor, block.base_end)

    parts.extend(base_lines[cursor:])
    clean = not conflicts
    return MergeResult(merged="".join(parts) if clean else None, clean=clean, conflicts=conflicts)
