"""Atomic multi-file apply: staging, journaled renames, rollback, isolation."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from researchos.common.config import get_settings
from researchos.common.paths import WorkspaceAccessError, resolve_in_workspace
from researchos.workspace import fs
from researchos.workspace.fs import FileOp, WorkspaceApplyError


def _ws(project_id: uuid.UUID) -> Path:
    return Path(get_settings().workspace_root) / str(project_id)


def _seed(project_id: uuid.UUID, files: dict[str, str]) -> None:
    for path, content in files.items():
        fs.write_file(project_id, path, content)


def test_apply_success_writes_deletes_creates() -> None:
    pid = uuid.uuid4()
    _seed(pid, {"keep.txt": "old\n", "gone.txt": "bye\n"})

    shas = fs.apply_files_atomic(
        pid,
        [
            FileOp(path="keep.txt", action="write", content="new\n"),
            FileOp(path="gone.txt", action="delete"),
            FileOp(path="sub/created.txt", action="write", content="hello\n"),
        ],
    )
    assert set(shas) == {"keep.txt", "sub/created.txt"}
    assert (_ws(pid) / "keep.txt").read_text(encoding="utf-8") == "new\n"
    assert not (_ws(pid) / "gone.txt").exists()
    assert (_ws(pid) / "sub" / "created.txt").read_text(encoding="utf-8") == "hello\n"
    # Staging is cleaned up on success.
    assert not list((_ws(pid) / ".ros-staging").iterdir())


def test_phase_a_failure_leaves_workspace_untouched() -> None:
    pid = uuid.uuid4()
    _seed(pid, {"a.txt": "A\n"})

    with pytest.raises(WorkspaceAccessError):
        fs.apply_files_atomic(
            pid,
            [
                FileOp(path="a.txt", action="write", content="changed\n"),
                FileOp(path="../escape.txt", action="write", content="x"),  # guard trips
            ],
        )
    assert (_ws(pid) / "a.txt").read_text(encoding="utf-8") == "A\n"
    assert not (Path(get_settings().workspace_root) / "escape.txt").exists()


def test_phase_b_failure_rolls_back_byte_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid.uuid4()
    _seed(pid, {"one.txt": "ONE\n", "two.txt": "TWO\n"})

    real_replace = os.replace
    state = {"calls": 0}

    def flaky_replace(src, dst):  # fail exactly once, mid-journal
        state["calls"] += 1
        if state["calls"] == 3:
            raise OSError("disk on fire")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    with pytest.raises(WorkspaceApplyError) as exc:
        fs.apply_files_atomic(
            pid,
            [
                FileOp(path="one.txt", action="write", content="one-new\n"),
                FileOp(path="two.txt", action="write", content="two-new\n"),
                FileOp(path="three.txt", action="write", content="three-new\n"),
            ],
        )
    assert exc.value.rolled_back is True
    # Originals restored byte-identically; the create never materialized.
    assert (_ws(pid) / "one.txt").read_text(encoding="utf-8") == "ONE\n"
    assert (_ws(pid) / "two.txt").read_text(encoding="utf-8") == "TWO\n"
    assert not (_ws(pid) / "three.txt").exists()


def test_staging_dir_hidden_and_unreachable() -> None:
    pid = uuid.uuid4()
    _seed(pid, {"visible.txt": "v\n"})
    staging = _ws(pid) / ".ros-staging" / "leftover"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "stage-0").write_text("secret", encoding="utf-8")

    names = [n["name"] for n in fs.build_tree(pid)]
    assert ".ros-staging" not in names
    with pytest.raises(WorkspaceAccessError):
        resolve_in_workspace(pid, ".ros-staging/leftover/stage-0")
    # Grep never descends into staging either.
    result = fs.grep_files(pid, "secret")
    assert result["matches"] == []


def test_stale_staging_cleanup() -> None:
    pid = uuid.uuid4()
    fs.ensure_workspace(pid)
    staging_root = _ws(pid) / ".ros-staging"
    stale = staging_root / "deadbeef"
    stale.mkdir(parents=True)
    old = time.time() - (25 * 60 * 60)
    os.utime(stale, (old, old))
    fresh = staging_root / "fresh"
    fresh.mkdir()

    fs.apply_files_atomic(pid, [FileOp(path="f.txt", action="write", content="x\n")])
    assert not stale.exists()
    assert fresh.exists()  # younger than 24h — kept
