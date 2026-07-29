"""Zotero integration DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SaveZoteroConnectionRequest(BaseModel):
    library_type: Literal["user", "group"] = "user"
    library_id: str = Field(min_length=1, max_length=64)
    api_key: str = Field(default="", max_length=512)
    enabled: bool = True
    include_collections: list[str] = Field(default_factory=list, max_length=50)


class ZoteroConnectionResponse(BaseModel):
    id: str
    library_type: Literal["user", "group"]
    library_id: str
    api_key_masked: str
    enabled: bool
    include_collections: list[str]
    last_library_version: int
    last_synced_at: datetime | None
    last_error: str | None


class ZoteroConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    username: str | None = None
    user_id: str | None = None
    library_access: bool = False
    latency_ms: int


class ZoteroSyncResponse(BaseModel):
    created: int
    updated: int
    linked: int
    skipped: int
    library_version: int
    last_synced_at: datetime
