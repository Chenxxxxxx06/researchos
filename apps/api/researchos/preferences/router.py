"""Preference endpoints: global (/users/me) and project-scoped."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import PreferencesPayload, ProjectPreferencesResponse, UserPreferencesResponse
from .service import PreferenceService

me_router = APIRouter(prefix="/users/me/preferences", tags=["preferences"])
project_router = APIRouter(prefix="/projects/{project_id}/preferences", tags=["preferences"])


@me_router.get("", response_model=UserPreferencesResponse)
async def get_my_preferences(user: CurrentUser, db: DbSession) -> UserPreferencesResponse:
    return await PreferenceService(db).get_me(user)


@me_router.put(
    "", response_model=UserPreferencesResponse, dependencies=[Depends(require_csrf)]
)
async def put_my_preferences(
    payload: PreferencesPayload, user: CurrentUser, db: DbSession
) -> UserPreferencesResponse:
    return await PreferenceService(db).put_me(user, payload)


@project_router.get("", response_model=ProjectPreferencesResponse)
async def get_project_preferences(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ProjectPreferencesResponse:
    return await PreferenceService(db).get_project(user, project_id)


@project_router.put(
    "", response_model=ProjectPreferencesResponse, dependencies=[Depends(require_csrf)]
)
async def put_project_preferences(
    project_id: uuid.UUID, payload: PreferencesPayload, user: CurrentUser, db: DbSession
) -> ProjectPreferencesResponse:
    return await PreferenceService(db).put_project(user, project_id, payload)
