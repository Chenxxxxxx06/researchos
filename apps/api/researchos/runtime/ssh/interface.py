"""SSH runtime interface and permission model — Phase 3 stubs only.

This module defines the *shape* of remote execution for a later phase. Nothing
here connects to a server, executes a command, or handles credentials. The real
implementation (Phase 4) must add credential encryption, approval gates, command
audit logging, timeouts, and cancellation before any remote execution is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class RuntimeAuthType(StrEnum):
    SSH_KEY = "ssh_key"
    PASSWORD = "password"  # noqa: S105 - identifier, not a secret


@dataclass(frozen=True)
class RuntimeProfile:
    """A saved remote target. Secrets are referenced, never stored here."""

    name: str
    host: str
    port: int
    username: str
    auth_type: RuntimeAuthType
    encrypted_key_ref: str | None = None
    default_workdir: str | None = None
    max_concurrent_jobs: int = 1
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandRequest:
    profile_name: str
    command: str
    workdir: str | None = None
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimePermission:
    """Whether a user may run on a profile, and whether approval is required."""

    can_execute: bool
    requires_approval: bool = True


@runtime_checkable
class RuntimeProvider(Protocol):
    """Future remote runtime. NOT implemented in Phase 3."""

    name: str

    async def execute(self, request: CommandRequest) -> None: ...


class UnavailableRuntimeProvider:
    """Default provider that refuses to execute (no remote runtime yet)."""

    name = "unavailable"

    async def execute(self, request: CommandRequest) -> None:
        raise NotImplementedError(
            "Remote SSH execution is not available in Phase 3. "
            "Only the interface and permission model are defined."
        )
