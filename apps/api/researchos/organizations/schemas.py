"""Organization DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from researchos.common.roles import OrgRole


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime


class OrganizationWithRole(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    role: OrgRole


class AddOrganizationMemberRequest(BaseModel):
    email: str
    role: OrgRole = OrgRole.MEMBER


class OrganizationMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: OrgRole
