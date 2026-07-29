"""LLM provider config endpoints — per-project, managed in Settings."""

from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from researchos.agents.llm.base import LLMMessage, LLMProvider, TextDelta, Usage
from researchos.agents.llm.openai_compatible import OpenAICompatibleProvider
from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.projects.service import ProjectService

from .models import LLMProviderConfig
from .schemas import (
    LLMConfigResponse,
    LLMConnectionTestResponse,
    SaveLLMConfigRequest,
)

router = APIRouter(prefix="/projects/{project_id}/settings/llm", tags=["settings-llm"])


def _mask(key: str) -> str:
    return f"****{key[-4:]}" if len(key) > 4 else "****"


@router.get("", response_model=list[LLMConfigResponse])
async def list_configs(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[LLMConfigResponse]:
    await ProjectService(db).ensure_access(user, project_id, ProjectRole.VIEWER)
    result = await db.execute(
        select(LLMProviderConfig).where(LLMProviderConfig.project_id == project_id)
    )
    return [
        LLMConfigResponse(
            id=str(c.id),
            name=c.name,
            provider_type=c.provider_type,
            base_url=c.base_url,
            model=c.model,
            api_key_masked=_mask(c.api_key),
            is_active=c.is_active,
            description=c.description,
        )
        for c in result.scalars().all()
    ]


@router.post("", response_model=LLMConfigResponse, dependencies=[Depends(require_csrf)])
async def save_config(
    project_id: uuid.UUID,
    payload: SaveLLMConfigRequest,
    user: CurrentUser,
    db: DbSession,
) -> LLMConfigResponse:
    await ProjectService(db).ensure_access(user, project_id, ProjectRole.ADMIN)

    existing = await db.scalar(
        select(LLMProviderConfig).where(
            LLMProviderConfig.project_id == project_id,
            LLMProviderConfig.name == payload.name,
        )
    )
    cfg = existing or LLMProviderConfig(project_id=project_id)
    cfg.name = payload.name
    cfg.provider_type = payload.provider_type
    cfg.base_url = payload.base_url.rstrip("/") if payload.base_url else ""
    cfg.model = payload.model
    if payload.api_key:
        cfg.api_key = payload.api_key
    cfg.is_active = payload.is_active
    cfg.description = payload.description
    if existing is None:
        db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return LLMConfigResponse(
        id=str(cfg.id),
        name=cfg.name,
        provider_type=cfg.provider_type,
        base_url=cfg.base_url,
        model=cfg.model,
        api_key_masked=_mask(cfg.api_key),
        is_active=cfg.is_active,
        description=cfg.description,
    )


@router.delete("/{config_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_config(
    project_id: uuid.UUID, config_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await ProjectService(db).ensure_access(user, project_id, ProjectRole.ADMIN)
    cfg = await db.get(LLMProviderConfig, config_id)
    if cfg is None or cfg.project_id != project_id:
        raise NotFoundError("LLM config not found.")
    await db.delete(cfg)
    await db.commit()


@router.post(
    "/{config_id}/test",
    response_model=LLMConnectionTestResponse,
    dependencies=[Depends(require_csrf)],
)
async def test_config(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> LLMConnectionTestResponse:
    """Perform a minimal real generation to verify endpoint, key and model.

    Returning a typed ``ok=false`` result keeps provider errors visible in the
    Settings UI without turning expected configuration failures into generic
    application errors.
    """

    await ProjectService(db).ensure_access(user, project_id, ProjectRole.ADMIN)
    cfg = await db.get(LLMProviderConfig, config_id)
    if cfg is None or cfg.project_id != project_id:
        raise NotFoundError("LLM config not found.")

    started = time.perf_counter()
    sample_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    try:
        provider: LLMProvider
        if cfg.provider_type == "anthropic":
            from researchos.agents.llm.anthropic import AnthropicProvider

            provider = AnthropicProvider(
                model=cfg.model or None,
                api_key=cfg.api_key or None,
                base_url=cfg.base_url or None,
            )
        else:
            provider = OpenAICompatibleProvider(
                base_url=cfg.base_url,
                model=cfg.model,
                api_key=cfg.api_key,
            )

        async with asyncio.timeout(30):
            async for event in provider.stream(
                messages=[
                    LLMMessage(
                        role="user",
                        content="Reply with exactly: ResearchOS connection OK",
                    )
                ],
                tools=[],
            ):
                if isinstance(event, TextDelta):
                    sample_parts.append(event.text)
                elif isinstance(event, Usage):
                    input_tokens += event.input_tokens
                    output_tokens += event.output_tokens
    except Exception as exc:  # noqa: BLE001 - this endpoint reports config failures
        latency_ms = int((time.perf_counter() - started) * 1000)
        message = str(exc).strip() or exc.__class__.__name__
        return LLMConnectionTestResponse(
            ok=False,
            provider_type=cfg.provider_type,
            model=cfg.model,
            latency_ms=latency_ms,
            message=message[:500],
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    sample = "".join(sample_parts).strip()
    return LLMConnectionTestResponse(
        ok=bool(sample),
        provider_type=cfg.provider_type,
        model=cfg.model,
        latency_ms=latency_ms,
        message="Model connection verified." if sample else "Provider returned an empty response.",
        sample=sample[:200] or None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
