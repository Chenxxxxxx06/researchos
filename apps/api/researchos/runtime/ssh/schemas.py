"""SSH runtime API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from researchos.workspace.schemas import FileContentResponse, TerminalRunResponse, TreeNode


class SSHProfileUpsert(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=120)
    auth_type: Literal["password", "ssh_key"]
    secret: str | None = Field(default=None, max_length=32_000)
    key_passphrase: str | None = Field(default=None, max_length=1024)
    known_hosts: str = Field(min_length=20, max_length=32_000)
    default_workdir: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def secret_required_for_create(self) -> SSHProfileUpsert:
        if self.id is None and not self.secret:
            raise ValueError("A password or private key is required for a new profile.")
        return self


class SSHProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    host: str
    port: int
    username: str
    auth_type: str
    credential_masked: str
    default_workdir: str
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SSHTestResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: int
    server_version: str | None = None


class SSHTreeResponse(BaseModel):
    root: str
    nodes: list[TreeNode]


class SSHFileSaveRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=1_000_000)
    base_sha: str | None = Field(default=None, min_length=64, max_length=64)


class SSHRunRequest(BaseModel):
    argv: list[str] = Field(min_length=1, max_length=64)
    cwd: str = Field(default=".", min_length=1, max_length=1024)
    timeout_seconds: int = Field(default=30, ge=1, le=60)


__all__ = [
    "FileContentResponse",
    "SSHFileSaveRequest",
    "SSHProfileResponse",
    "SSHProfileUpsert",
    "SSHRunRequest",
    "SSHTestResponse",
    "SSHTreeResponse",
    "TerminalRunResponse",
]
