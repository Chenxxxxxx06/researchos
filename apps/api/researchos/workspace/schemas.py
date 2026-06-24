"""Workspace DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TreeNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "dir"]
    children: list[TreeNode] = []


class TreeResponse(BaseModel):
    root: str
    nodes: list[TreeNode]


class FileContentResponse(BaseModel):
    path: str
    binary: bool
    too_large: bool = False
    size: int
    sha: str | None
    content: str | None


TreeNode.model_rebuild()
