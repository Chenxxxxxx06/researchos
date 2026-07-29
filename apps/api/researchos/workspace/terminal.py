"""Bounded real-process execution for the browser IDE terminal.

This is deliberately argv-based and never invokes a shell. It provides real
workspace execution while excluding shell expansion, pipes, redirects and
background process syntax. Interactive PTY and SSH executors remain separate
adapters.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from researchos.common.config import get_settings
from researchos.common.errors import AppError, ValidationError
from researchos.common.paths import resolve_in_workspace, workspace_root_for

_ALLOWED_EXECUTABLES = frozenset(
    {
        "git",
        "node",
        "npm",
        "npx",
        "pnpm",
        "python",
        "python3",
        "pytest",
    }
)
_READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {"branch", "diff", "log", "rev-parse", "show", "status"}
)
_MAX_OUTPUT_BYTES = 100_000


async def run_command(
    project_id: uuid.UUID,
    *,
    argv: list[str],
    cwd: str,
    timeout_seconds: int,
) -> dict:
    settings = get_settings()
    if settings.environment != "local" or not settings.workspace_terminal_enabled:
        raise ValidationError(
            "The browser terminal is local-development only. Use an isolated runtime "
            "for staging or production."
        )

    executable = argv[0].strip() if argv else ""
    if sum(len(value) for value in argv) > 16_000 or any(len(value) > 4096 for value in argv):
        raise ValidationError("Terminal arguments are too large.")
    if (
        not executable
        or Path(executable).name != executable
        or executable.lower() not in _ALLOWED_EXECUTABLES
    ):
        raise ValidationError(
            "Executable is not allowed in the browser terminal.",
            details={"allowed": sorted(_ALLOWED_EXECUTABLES)},
        )

    if executable.lower() == "git":
        subcommand = argv[1].lower() if len(argv) > 1 else ""
        if subcommand not in _READ_ONLY_GIT_SUBCOMMANDS:
            raise ValidationError(
                "Only read-only Git commands are allowed here. Use Source Control "
                "for commits and patch application."
            )

    resolved_cwd = resolve_in_workspace(project_id, cwd)
    root = workspace_root_for(project_id).resolve()
    if not resolved_cwd.exists():
        raise ValidationError("Terminal working directory does not exist.")
    if not resolved_cwd.is_dir():
        raise ValidationError("Terminal working directory must be a directory.")

    safe_env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
    }
    safe_env["PYTHONUNBUFFERED"] = "1"
    started = time.perf_counter()
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(resolved_cwd),
            env=safe_env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise AppError(
            f"Unable to execute command: {exc}",
            code="terminal_execution_failed",
            http_status=502,
        ) from exc
    stdout_task = asyncio.create_task(_read_limited(process.stdout, process))
    stderr_task = asyncio.create_task(_read_limited(process.stderr, process))
    timed_out = False
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
    except TimeoutError:
        timed_out = True
        _kill_if_running(process)
        await process.wait()

    (stdout_raw, stdout_truncated), (stderr_raw, stderr_truncated) = await asyncio.gather(
        stdout_task, stderr_task
    )

    def decode(raw: bytes, truncated: bool) -> str:
        suffix = "\n… output truncated; process terminated" if truncated else ""
        return raw.decode("utf-8", errors="replace") + suffix

    relative_cwd = resolved_cwd.relative_to(root).as_posix() or "."
    return {
        "argv": argv,
        "cwd": relative_cwd,
        "exit_code": process.returncode,
        "stdout": decode(stdout_raw, stdout_truncated),
        "stderr": decode(stderr_raw, stderr_truncated),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "timed_out": timed_out,
    }


async def _read_limited(
    stream: asyncio.StreamReader | None,
    process: asyncio.subprocess.Process,
) -> tuple[bytes, bool]:
    if stream is None:
        return b"", False
    output = bytearray()
    truncated = False
    while chunk := await stream.read(8192):
        remaining = _MAX_OUTPUT_BYTES - len(output)
        if remaining > 0:
            output.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True
            _kill_if_running(process)
    return bytes(output), truncated


def _kill_if_running(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
