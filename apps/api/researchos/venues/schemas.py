"""Schemas for venue deadlines."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VenueDeadline(BaseModel):
    uid: str
    title: str
    description: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    url: str | None = None


class VenueDeadlineFeed(BaseModel):
    source_name: str
    source_url: str
    fetched_at: datetime
    items: list[VenueDeadline]
