"""Workspace DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "dir"]
    children: list[TreeNode] = []


class TreeResponse(BaseModel):
    root: str
    nodes: list[TreeNode]


class LocalWorkspaceConfigResponse(BaseModel):
    root: str
    default_root: str
    uses_default: bool
    available: bool
    recent_roots: list[str]


class SetLocalWorkspaceRequest(BaseModel):
    root_path: str = Field(min_length=1, max_length=2048)


class FileContentResponse(BaseModel):
    path: str
    binary: bool
    too_large: bool = False
    size: int
    sha: str | None
    content: str | None


class SaveFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=1_000_000)
    base_sha: str | None = Field(default=None, min_length=64, max_length=64)


class TerminalRunRequest(BaseModel):
    argv: list[str] = Field(min_length=1, max_length=64)
    cwd: str = Field(default=".", min_length=1, max_length=1024)
    timeout_seconds: int = Field(default=30, ge=1, le=60)


class TerminalRunResponse(BaseModel):
    argv: list[str]
    cwd: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


class GrepMatch(BaseModel):
    path: str
    line: int
    preview: str


class GrepResponse(BaseModel):
    matches: list[GrepMatch]
    truncated: bool


TreeNode.model_rebuild()
