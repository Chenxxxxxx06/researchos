"""Host-key verified AsyncSSH adapter with bounded SFTP and command access."""

from __future__ import annotations

import asyncio
import hashlib
import json
import posixpath
import shlex
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from typing import Any

import asyncssh

from researchos.common.errors import AppError, ConflictError, ValidationError
from researchos.common.paths import is_denied
from researchos.common.secrets import decrypt_secret
from researchos.workspace.terminal import _ALLOWED_EXECUTABLES, _READ_ONLY_GIT_SUBCOMMANDS

from .models import SSHProfile

_MAX_FILE_BYTES = 1_000_000
_MAX_OUTPUT_BYTES = 100_000
_MAX_TREE_ENTRIES = 5_000
_MAX_TREE_DEPTH = 8


def remote_join(root: str, relative: str) -> str:
    """Resolve a POSIX path below a configured remote root."""

    clean_root = posixpath.normpath(root)
    if not clean_root.startswith("/"):
        raise ValidationError("Remote workdir must be an absolute POSIX path.")
    if not relative or relative == ".":
        return clean_root
    if PurePosixPath(relative).is_absolute():
        raise ValidationError("Remote paths must be relative to the configured workdir.")
    candidate = posixpath.normpath(posixpath.join(clean_root, relative))
    if candidate != clean_root and not candidate.startswith(clean_root.rstrip("/") + "/"):
        raise ValidationError("Remote path escapes the configured workdir.")
    rel = posixpath.relpath(candidate, clean_root)
    if rel != "." and is_denied(rel):
        raise ValidationError("This remote file is protected and cannot be accessed.")
    return candidate


def _credentials(profile: SSHProfile) -> tuple[str | None, list[Any] | None]:
    raw = json.loads(decrypt_secret(profile.encrypted_credentials))
    if profile.auth_type == "password":
        return str(raw["secret"]), None
    try:
        key = asyncssh.import_private_key(
            str(raw["secret"]), passphrase=raw.get("key_passphrase") or None
        )
    except (ValueError, asyncssh.KeyImportError) as exc:
        raise ValidationError("The saved SSH private key could not be loaded.") from exc
    return None, [key]


@asynccontextmanager
async def connect(profile: SSHProfile) -> AsyncIterator[asyncssh.SSHClientConnection]:
    password, client_keys = _credentials(profile)
    try:
        async with asyncssh.connect(
            profile.host,
            port=profile.port,
            username=profile.username,
            password=password,
            client_keys=client_keys,
            known_hosts=profile.known_hosts.encode("utf-8"),
            agent_path=None,
            config=[],
            login_timeout=10,
        ) as connection:
            yield connection
    except (OSError, asyncssh.Error) as exc:
        raise AppError(
            f"SSH connection failed: {exc}", code="ssh_connection_failed", http_status=502
        ) from exc


async def test_connection(profile: SSHProfile) -> dict:
    started = time.perf_counter()
    async with connect(profile) as connection:
        async with connection.start_sftp_client() as sftp:
            root = await sftp.realpath(profile.default_workdir)
            if not await sftp.isdir(root):
                raise ValidationError("The configured remote workdir is not a directory.")
        return {
            "ok": True,
            "message": "Host key, authentication, and remote workdir verified.",
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "server_version": str(connection.get_extra_info("server_version", "")),
        }


async def build_tree(profile: SSHProfile) -> dict:
    async with connect(profile) as connection, connection.start_sftp_client() as sftp:
        root = await _verified_root(sftp, profile)
        counter = [0]

        async def walk(directory: str, depth: int) -> list[dict]:
            if depth > _MAX_TREE_DEPTH or counter[0] >= _MAX_TREE_ENTRIES:
                return []
            nodes: list[dict] = []
            async for entry in sftp.scandir(directory):
                name = str(entry.filename)
                if name in {".", ".."}:
                    continue
                path = posixpath.join(directory, name)
                relative = posixpath.relpath(path, root)
                if is_denied(relative):
                    continue
                counter[0] += 1
                if counter[0] > _MAX_TREE_ENTRIES:
                    break
                directory_entry = await sftp.isdir(path)
                node: dict[str, Any] = {
                    "name": name,
                    "path": relative,
                    "type": "dir" if directory_entry else "file",
                }
                if directory_entry:
                    node["children"] = await walk(path, depth + 1)
                nodes.append(node)
            return sorted(nodes, key=lambda item: (item["type"] != "dir", item["name"].lower()))

        return {"root": root, "nodes": await walk(root, 0)}


async def read_file(profile: SSHProfile, relative: str) -> dict:
    async with connect(profile) as connection, connection.start_sftp_client() as sftp:
        root = await _verified_root(sftp, profile)
        path = await _verified_path(sftp, root, relative)
        attrs = await sftp.stat(path)
        size = int(attrs.size or 0)
        if size > _MAX_FILE_BYTES:
            return {
                "path": relative,
                "binary": False,
                "too_large": True,
                "size": size,
                "sha": None,
                "content": None,
            }
        async with sftp.open(path, "rb") as handle:
            raw_data = await handle.read(_MAX_FILE_BYTES + 1)
        raw = raw_data.encode("utf-8") if isinstance(raw_data, str) else raw_data
        binary = b"\x00" in raw[:8192]
        return {
            "path": relative,
            "binary": binary,
            "too_large": False,
            "size": len(raw),
            "sha": hashlib.sha256(raw).hexdigest(),
            "content": None if binary else raw.decode("utf-8", errors="replace"),
        }


async def write_file(
    profile: SSHProfile, relative: str, content: str, base_sha: str | None
) -> dict:
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_FILE_BYTES:
        raise ValidationError("Remote file exceeds the 1 MB editor limit.")
    async with connect(profile) as connection, connection.start_sftp_client() as sftp:
        root = await _verified_root(sftp, profile)
        unresolved = remote_join(root, relative)
        parent = await sftp.realpath(posixpath.dirname(unresolved))
        if parent != root and not parent.startswith(root.rstrip("/") + "/"):
            raise ValidationError("Remote path escapes the configured workdir.")
        exists = await sftp.exists(unresolved)
        actual_sha: str | None = None
        if exists:
            path = await _verified_path(sftp, root, relative)
            async with sftp.open(path, "rb") as handle:
                current_data = await handle.read(_MAX_FILE_BYTES + 1)
            current = (
                current_data.encode("utf-8") if isinstance(current_data, str) else current_data
            )
            actual_sha = hashlib.sha256(current).hexdigest()
        if actual_sha != base_sha:
            raise ConflictError(
                "Remote file changed. Reload it before saving.",
                code="ssh_file_conflict",
                details={"path": relative, "expected_sha": base_sha, "actual_sha": actual_sha},
            )
        async with sftp.open(unresolved, "wb") as handle:
            await handle.write(encoded)
    return {
        "path": relative,
        "binary": False,
        "too_large": False,
        "size": len(encoded),
        "sha": hashlib.sha256(encoded).hexdigest(),
        "content": content,
    }


async def run_command(profile: SSHProfile, argv: list[str], cwd: str, timeout_seconds: int) -> dict:
    _validate_argv(argv)
    remote_cwd = remote_join(profile.default_workdir, cwd)
    command = f"cd -- {shlex.quote(remote_cwd)} && exec {shlex.join(argv)}"
    started = time.perf_counter()
    timed_out = False
    try:
        async with connect(profile) as connection:
            async with asyncio.timeout(timeout_seconds):
                result = await connection.run(command, check=False)
    except TimeoutError:
        timed_out = True
        result = None
    duration = int((time.perf_counter() - started) * 1000)
    stdout = "" if result is None else str(result.stdout)
    stderr = "Command timed out." if result is None else str(result.stderr)
    return {
        "argv": argv,
        "cwd": cwd,
        "exit_code": None if result is None else result.exit_status,
        "stdout": stdout[:_MAX_OUTPUT_BYTES],
        "stderr": stderr[:_MAX_OUTPUT_BYTES],
        "duration_ms": duration,
        "timed_out": timed_out,
    }


async def _verified_root(sftp: Any, profile: SSHProfile) -> str:
    root = posixpath.normpath(str(await sftp.realpath(profile.default_workdir)))
    if not root.startswith("/") or not await sftp.isdir(root):
        raise ValidationError("The configured remote workdir is unavailable.")
    return root


async def _verified_path(sftp: Any, root: str, relative: str) -> str:
    candidate = remote_join(root, relative)
    real = posixpath.normpath(str(await sftp.realpath(candidate)))
    if real != root and not real.startswith(root.rstrip("/") + "/"):
        raise ValidationError("Remote symlink escapes the configured workdir.")
    return real


def _validate_argv(argv: list[str]) -> None:
    executable = argv[0].strip() if argv else ""
    if sum(len(value) for value in argv) > 16_000 or any(len(value) > 4096 for value in argv):
        raise ValidationError("Terminal arguments are too large.")
    if (
        not executable
        or PurePosixPath(executable).name != executable
        or executable.lower() not in _ALLOWED_EXECUTABLES
    ):
        raise ValidationError(
            "Executable is not allowed in the SSH terminal.",
            details={"allowed": sorted(_ALLOWED_EXECUTABLES)},
        )
    if executable.lower() == "git" and (
        len(argv) < 2 or argv[1].lower() not in _READ_ONLY_GIT_SUBCOMMANDS
    ):
        raise ValidationError("Only read-only Git commands are allowed in the SSH terminal.")
