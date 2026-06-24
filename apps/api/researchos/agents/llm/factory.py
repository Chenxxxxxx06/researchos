"""LLM provider selection by configuration. Default is the mock provider."""

from __future__ import annotations

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .base import LLMProvider
from .mock import MockLLMProvider


def get_llm_provider() -> LLMProvider:
    name = get_settings().llm_provider
    if name == "mock":
        return MockLLMProvider()
    if name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider()
    raise AppError(f"Unknown LLM provider: {name}", code="config_error", http_status=500)
