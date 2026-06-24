"""Project DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from researchos.common.roles import ProjectRole, ProjectStatus


class CreateProjectRequest(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    field: str | None = Field(default=None, max_length=120)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    field: str | None = Field(default=None, max_length=120)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    field: str | None
    status: ProjectStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AddProjectMemberRequest(BaseModel):
    email: str
    role: ProjectRole = ProjectRole.RESEARCHER


class UpdateProjectMemberRequest(BaseModel):
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: ProjectRole
