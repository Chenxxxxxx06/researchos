"""LLM provider selection.

Priority: active project DB config → env-variable fallback → mock (default).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from researchos.common.config import get_settings

from .base import LLMProvider
from .mock import MockLLMProvider


async def get_llm_provider(project_id: uuid.UUID | None = None) -> LLMProvider:
    """Return an LLM provider for the given project.

    When ``project_id`` is provided, the active DB config for that project is
    used first. Falls back to environment variables, then the mock provider.
    """

    # 1. Active DB config per project (only if project_id given).
    if project_id is not None:
        from researchos.common.db import get_sessionmaker
        from researchos.llm_config.models import LLMProviderConfig

        async with get_sessionmaker()() as db:
            cfg = await db.scalar(
                select(LLMProviderConfig)
                .where(
                    LLMProviderConfig.project_id == project_id,
                    LLMProviderConfig.is_active.is_(True),
                )
                # Deterministic pick: most recently updated active row wins.
                .order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id)
                .limit(1)
            )
        if cfg is not None:
            from .openai_compatible import OpenAICompatibleProvider

            if cfg.provider_type == "anthropic":
                from .anthropic import AnthropicProvider

                # Empty strings mean "use env" (matches the llm_config router's
                # empty-api_key-preserves-stored-key convention).
                return AnthropicProvider(
                    model=cfg.model or None,
                    api_key=cfg.api_key or None,
                    base_url=cfg.base_url or None,
                )
            return OpenAICompatibleProvider(
                base_url=cfg.base_url,
                model=cfg.model,
                api_key=cfg.api_key,
            )

    # 2. Environment-variable fallback.
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider()
    if settings.llm_provider == "openai_compatible":
        from .openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider()

    # 3. Safe default: mock (always works, no calls, no cost).
    return MockLLMProvider()
