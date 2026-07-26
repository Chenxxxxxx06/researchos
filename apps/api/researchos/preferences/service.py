"""Preference resolution and per-scope upsert.

Rows are strictly personal: every query filters ``user_id = actor.id``, so no
cross-user access exists by construction. Effective resolution is field-wise
project -> global -> defaults; ``extra`` merges per key (project wins).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import ProjectRole
from researchos.figures.presets import DEFAULT_STYLE_SLUG
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .models import UserPreference
from .schemas import (
    EffectivePreferences,
    PreferencesPayload,
    ProjectPreferencesResponse,
    UserPreferencesResponse,
)

# zh-CN matches the frontend's current default locale.
DEFAULTS = EffectivePreferences(
    theme="system", language="zh-CN", figure_style_slug=DEFAULT_STYLE_SLUG, extra={}
)


class PreferenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    # --- rows ----------------------------------------------------------------
    async def _get_row(
        self, user_id: uuid.UUID, project_id: uuid.UUID | None
    ) -> UserPreference | None:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        if project_id is None:
            stmt = stmt.where(UserPreference.project_id.is_(None))
        else:
            stmt = stmt.where(UserPreference.project_id == project_id)
        return await self.db.scalar(stmt)

    @staticmethod
    def _payload(row: UserPreference | None) -> PreferencesPayload | None:
        if row is None:
            return None
        return PreferencesPayload(
            theme=row.theme,
            language=row.language,
            figure_style_slug=row.figure_style_slug,
            extra=dict(row.extra_json or {}),
        )

    @staticmethod
    def _merge(
        project: PreferencesPayload | None, global_: PreferencesPayload | None
    ) -> EffectivePreferences:
        def pick(field: str) -> object:
            for scope in (project, global_):
                if scope is not None and getattr(scope, field) is not None:
                    return getattr(scope, field)
            return getattr(DEFAULTS, field)

        extra: dict = {}
        if global_ is not None:
            extra.update(global_.extra)
        if project is not None:
            extra.update(project.extra)
        return EffectivePreferences(
            theme=pick("theme"),
            language=pick("language"),
            figure_style_slug=pick("figure_style_slug"),
            extra=extra,
        )

    async def _put_row(
        self, user_id: uuid.UUID, project_id: uuid.UUID | None, payload: PreferencesPayload
    ) -> UserPreference:
        """Full replacement of the scope's row (omitted field => NULL)."""

        row = await self._get_row(user_id, project_id)
        if row is None:
            row = UserPreference(user_id=user_id, project_id=project_id)
            self.db.add(row)
        row.theme = payload.theme
        row.language = payload.language
        row.figure_style_slug = payload.figure_style_slug
        row.extra_json = dict(payload.extra)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    # --- global scope --------------------------------------------------------
    async def get_me(self, actor: User) -> UserPreferencesResponse:
        global_row = self._payload(await self._get_row(actor.id, None))
        return UserPreferencesResponse(
            effective=self._merge(None, global_row), global_=global_row
        )

    async def put_me(self, actor: User, payload: PreferencesPayload) -> UserPreferencesResponse:
        row = await self._put_row(actor.id, None, payload)
        global_row = self._payload(row)
        return UserPreferencesResponse(
            effective=self._merge(None, global_row), global_=global_row
        )

    # --- project scope (personal rows; any member) ---------------------------
    async def get_project(
        self, actor: User, project_id: uuid.UUID
    ) -> ProjectPreferencesResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        project_row = self._payload(await self._get_row(actor.id, project_id))
        global_row = self._payload(await self._get_row(actor.id, None))
        return ProjectPreferencesResponse(
            effective=self._merge(project_row, global_row),
            project=project_row,
            global_=global_row,
        )

    async def put_project(
        self, actor: User, project_id: uuid.UUID, payload: PreferencesPayload
    ) -> ProjectPreferencesResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        await self._put_row(actor.id, project_id, payload)
        return await self.get_project(actor, project_id)

    # --- cross-context helper -------------------------------------------------
    async def figure_style_for_user(
        self, user_id: uuid.UUID, project_id: uuid.UUID | None
    ) -> str:
        """Effective figure style slug for a user id (no access checks)."""

        if project_id is not None:
            row = await self._get_row(user_id, project_id)
            if row is not None and row.figure_style_slug is not None:
                return row.figure_style_slug
        row = await self._get_row(user_id, None)
        if row is not None and row.figure_style_slug is not None:
            return row.figure_style_slug
        return DEFAULT_STYLE_SLUG
