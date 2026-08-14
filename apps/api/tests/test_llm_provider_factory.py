"""Integration tests for database-backed LLM provider resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.llm.factory import get_llm_provider
from researchos.agents.llm.openai_compatible import OpenAICompatibleProvider
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.secrets import encrypt_secret
from researchos.identity.service import AuthService
from researchos.llm_config.models import LLMProviderConfig
from researchos.projects.service import ProjectService


async def _setup_project(db: AsyncSession, email: str):
    user, organization = await AuthService(db).register(
        email=email,
        password="password123",
        display_name="Factory tester",
    )
    project = await ProjectService(db).create_project(
        user,
        organization_id=organization.id,
        name="Factory project",
        description=None,
        field=None,
    )
    return project, user


async def _add_config(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    model: str,
    active: bool,
    base_url: str = "https://llm.example.test/v1",
) -> LLMProviderConfig:
    config = LLMProviderConfig(
        project_id=project_id,
        name=model,
        provider_type="openai_compatible",
        base_url=base_url,
        model=model,
        api_key=encrypt_secret("factory-test-key"),
        is_active=active,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def test_explicit_config_id_selects_that_enabled_config(db_session: AsyncSession) -> None:
    project, _user = await _setup_project(db_session, "factory-explicit@example.com")
    first = await _add_config(
        db_session,
        project.id,
        model="model-a",
        active=True,
        base_url="https://first.example.test/v1",
    )
    second = await _add_config(db_session, project.id, model="model-b", active=True)

    provider = await get_llm_provider(project.id, config_id=first.id)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "model-a"
    assert provider.base_url == "https://first.example.test/v1"
    assert second.id != first.id


async def test_default_selection_uses_most_recent_enabled_config(
    db_session: AsyncSession,
) -> None:
    project, _user = await _setup_project(db_session, "factory-default@example.com")
    older = await _add_config(db_session, project.id, model="model-old", active=True)
    newer = await _add_config(
        db_session,
        project.id,
        model="model-new",
        active=True,
        base_url="https://newer.example.test/v1",
    )
    older.updated_at = datetime.now(UTC) - timedelta(days=1)
    newer.updated_at = datetime.now(UTC)
    await db_session.commit()

    provider = await get_llm_provider(project.id)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "model-new"
    assert provider.base_url == "https://newer.example.test/v1"


async def test_explicit_inactive_config_raises_validation_error(
    db_session: AsyncSession,
) -> None:
    project, _user = await _setup_project(db_session, "factory-inactive@example.com")
    inactive = await _add_config(db_session, project.id, model="model-off", active=False)

    with pytest.raises(ValidationError, match="selected LLM config is not active"):
        await get_llm_provider(project.id, config_id=inactive.id)


async def test_explicit_cross_project_config_raises_not_found(db_session: AsyncSession) -> None:
    project, _user = await _setup_project(db_session, "factory-cross@example.com")
    other_project, _other_user = await _setup_project(
        db_session, "factory-cross-other@example.com"
    )
    config = await _add_config(db_session, other_project.id, model="model-other", active=True)

    with pytest.raises(NotFoundError, match="LLM config not found"):
        await get_llm_provider(project.id, config_id=config.id)


async def test_explicit_missing_config_raises_not_found(db_session: AsyncSession) -> None:
    project, _user = await _setup_project(db_session, "factory-missing@example.com")

    with pytest.raises(NotFoundError, match="LLM config not found"):
        await get_llm_provider(project.id, config_id=uuid.uuid4())


async def test_explicit_config_requires_project() -> None:
    with pytest.raises(ValidationError, match="project is required"):
        await get_llm_provider(config_id=uuid.uuid4())
