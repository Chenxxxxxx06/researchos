"""Security-boundary tests for browser terminal command validation."""

import uuid

import pytest

from researchos.common.errors import ValidationError
from researchos.workspace import terminal as terminal_runner
from researchos.workspace.terminal import run_command


async def test_terminal_rejects_shell_executable() -> None:
    with pytest.raises(ValidationError, match="not allowed"):
        await run_command(
            uuid.uuid4(),
            argv=["powershell", "-Command", "Get-ChildItem"],
            cwd=".",
            timeout_seconds=5,
        )


async def test_terminal_rejects_git_write_subcommand() -> None:
    with pytest.raises(ValidationError, match="read-only Git"):
        await run_command(
            uuid.uuid4(),
            argv=["git", "commit", "-m", "not-allowed"],
            cwd=".",
            timeout_seconds=5,
        )


async def test_terminal_rejects_executable_path() -> None:
    with pytest.raises(ValidationError, match="not allowed"):
        await run_command(
            uuid.uuid4(),
            argv=["C:/Windows/System32/cmd.exe", "/c", "dir"],
            cwd=".",
            timeout_seconds=5,
        )


async def test_terminal_runs_real_read_only_git_process(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(terminal_runner, "workspace_root_for", lambda _project_id: tmp_path)
    monkeypatch.setattr(
        terminal_runner,
        "resolve_in_workspace",
        lambda _project_id, _cwd: tmp_path,
    )
    result = await run_command(
        uuid.uuid4(),
        argv=["git", "status", "--short"],
        cwd=".",
        timeout_seconds=5,
    )
    assert result["argv"] == ["git", "status", "--short"]
    assert result["cwd"] == "."
    assert isinstance(result["exit_code"], int)
    assert result["duration_ms"] >= 0
