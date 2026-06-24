"""Skills marketplace and skill-builder endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .manifest import ALLOWED_TOOLS
from .schemas import (
    CustomSkillRequest,
    InstalledSkillResponse,
    SkillCatalogItem,
    SkillDetailResponse,
    ToggleSkillRequest,
    ValidateManifestResponse,
)
from .service import SkillService

router = APIRouter(prefix="/projects/{project_id}/skills", tags=["skills"])


@router.get("/catalog", response_model=list[SkillCatalogItem])
async def list_catalog(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[SkillCatalogItem]:
    return await SkillService(db).list_catalog(user, project_id)


@router.get("/installed", response_model=list[InstalledSkillResponse])
async def list_installed(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[InstalledSkillResponse]:
    return await SkillService(db).list_installed(user, project_id)


@router.get("/allowed-tools", response_model=list[str])
async def allowed_tools() -> list[str]:
    return list(ALLOWED_TOOLS)


@router.post(
    "/validate",
    response_model=ValidateManifestResponse,
    dependencies=[Depends(require_csrf)],
)
async def validate_manifest(
    project_id: uuid.UUID, payload: CustomSkillRequest, user: CurrentUser, db: DbSession
) -> ValidateManifestResponse:
    errors = SkillService(db).validate(payload)
    return ValidateManifestResponse(valid=not errors, errors=errors)


@router.post(
    "/custom",
    response_model=SkillDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_custom_skill(
    project_id: uuid.UUID, payload: CustomSkillRequest, user: CurrentUser, db: DbSession
) -> SkillDetailResponse:
    return await SkillService(db).create_custom(user, project_id, payload)


@router.put(
    "/custom/{slug}",
    response_model=SkillDetailResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_custom_skill(
    project_id: uuid.UUID,
    slug: str,
    payload: CustomSkillRequest,
    user: CurrentUser,
    db: DbSession,
) -> SkillDetailResponse:
    return await SkillService(db).update_custom(user, project_id, slug, payload)


@router.get("/{slug}", response_model=SkillDetailResponse)
async def get_skill(
    project_id: uuid.UUID, slug: str, user: CurrentUser, db: DbSession
) -> SkillDetailResponse:
    return await SkillService(db).get_skill(user, project_id, slug)


@router.post(
    "/{slug}/install", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
async def install_skill(project_id: uuid.UUID, slug: str, user: CurrentUser, db: DbSession) -> None:
    await SkillService(db).install(user, project_id, slug)


@router.post(
    "/{slug}/toggle", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
async def toggle_skill(
    project_id: uuid.UUID,
    slug: str,
    payload: ToggleSkillRequest,
    user: CurrentUser,
    db: DbSession,
) -> None:
    await SkillService(db).toggle(user, project_id, slug, enabled=payload.enabled)
