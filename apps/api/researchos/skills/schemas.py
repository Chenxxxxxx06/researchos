"""Skill DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import SkillModule, SkillVisibility


class SkillCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    author: str
    category: str
    visibility: SkillVisibility
    modules: list[str]
    installed: bool
    enabled: bool


class SkillDetailResponse(BaseModel):
    slug: str
    name: str
    description: str
    author: str
    category: str
    visibility: SkillVisibility
    version: str
    modules: list[str]
    prompt_template: str
    workflow: list[str]
    tool_permissions: list[str]
    config_schema: dict
    installed: bool
    enabled: bool


class InstalledSkillResponse(BaseModel):
    slug: str
    name: str
    version: str
    enabled: bool


class ToggleSkillRequest(BaseModel):
    enabled: bool


class ValidateManifestResponse(BaseModel):
    valid: bool
    errors: list[str]


class CustomSkillRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    version: str = "1.0.0"
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="general", max_length=60)
    modules: list[SkillModule] = Field(default_factory=list)
    prompt_template: str = Field(default="", max_length=20_000)
    workflow: list[str] = Field(default_factory=list)
    tool_permissions: list[str] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)
