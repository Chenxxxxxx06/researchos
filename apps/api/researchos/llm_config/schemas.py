"""LLM provider config DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMConfigResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    model: str
    api_key_masked: str  # last 4 chars only
    is_active: bool
    description: str | None


class SaveLLMConfigRequest(BaseModel):
    name: str = Field(default="default", max_length=100)
    provider_type: str = Field(default="openai_compatible", max_length=30)
    base_url: str = Field(default="https://api.openai.com/v1", max_length=1024)
    model: str = Field(default="gpt-4o", max_length=120)
    api_key: str = Field(default="", max_length=512)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=500)
