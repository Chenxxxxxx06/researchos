"""Citation organizer API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CitationAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    agent_run_id: uuid.UUID
    items_json: list
    duplicate_groups_json: list
    missing_field_count: int
    bibtex_text: str
    created_by: uuid.UUID
    created_at: datetime
