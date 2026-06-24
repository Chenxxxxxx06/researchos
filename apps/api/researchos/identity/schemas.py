"""Identity DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from researchos.common.roles import OrgRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    created_at: datetime


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: OrgRole


class MeResponse(BaseModel):
    user: UserResponse
    organizations: list[OrganizationSummary]


class RegisterResponse(BaseModel):
    user: UserResponse
    organization: OrganizationSummary
