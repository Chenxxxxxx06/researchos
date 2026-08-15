"""LLM provider config DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class LLMConfigResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    model: str
    api_key_masked: str  # last 4 chars only
    is_active: bool
    description: str | None


class CreateLLMConfigRequest(BaseModel):
    name: str = Field(default="default", max_length=100)
    provider_type: str = Field(default="openai_compatible", max_length=30)
    base_url: str = Field(default="https://api.openai.com/v1", max_length=1024)
    model: str = Field(default="gpt-4o", max_length=120)
    api_key: str = Field(default="", max_length=512)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=500)


class UpdateLLMConfigRequest(BaseModel):
    """Partial update payload.

    An omitted field preserves the stored value. An empty ``api_key`` also
    preserves the encrypted secret so the settings form can submit unchanged
    credentials without reading the secret back into the browser.
    """

    name: str | None = Field(default=None, max_length=100)
    provider_type: str | None = Field(default=None, max_length=30)
    base_url: str | None = Field(default=None, max_length=1024)
    model: str | None = Field(default=None, max_length=120)
    api_key: str | None = Field(default=None, max_length=512)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _reject_null_required_fields(self) -> UpdateLLMConfigRequest:
        required = ("name", "provider_type", "base_url", "model", "is_active")
        for field_name in required:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class LLMConnectionTestResponse(BaseModel):
    ok: bool
    provider_type: str
    model: str
    latency_ms: int
    message: str
    sample: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
