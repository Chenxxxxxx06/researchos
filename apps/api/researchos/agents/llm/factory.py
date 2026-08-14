"""LLM provider selection.

Priority: active project DB config → env-variable fallback → mock (default).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.secrets import decrypt_secret
from researchos.llm_config.models import LLMProviderConfig

from .base import LLMProvider
from .mock import MockLLMProvider
from .openai_compatible import OpenAICompatibleProvider


def _provider_from_config(cfg: LLMProviderConfig) -> LLMProvider:
    if cfg.provider_type == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(
            model=cfg.model or None,
            api_key=decrypt_secret(cfg.api_key) or None,
            base_url=cfg.base_url or None,
        )
    return OpenAICompatibleProvider(
        base_url=cfg.base_url,
        model=cfg.model,
        api_key=decrypt_secret(cfg.api_key),
    )


async def get_llm_provider(
    project_id: uuid.UUID | None = None,
    *,
    config_id: uuid.UUID | None = None,
) -> LLMProvider:
    """Return an LLM provider for the given project.

    When ``project_id`` is provided, the active DB config for that project is
    used first. Falls back to environment variables, then the mock provider.
    """

    if config_id is not None and project_id is None:
        raise ValidationError("A project is required for an explicit LLM configuration.")

    # 1. DB config per project (only if project_id given).
    if project_id is not None:
        from researchos.common.db import get_sessionmaker

        async with get_sessionmaker()() as db:
            if config_id is not None:
                cfg = await db.get(LLMProviderConfig, config_id)
                if cfg is None or cfg.project_id != project_id:
                    raise NotFoundError("LLM config not found.")
                if not cfg.is_active:
                    raise ValidationError("The selected LLM config is not active.")
                return _provider_from_config(cfg)

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
            return _provider_from_config(cfg)

    # 2. Environment-variable fallback.
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider()
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider()

    # 3. Safe default: mock (always works, no calls, no cost).
    return MockLLMProvider()
