"""Authorization, persistence, and audit layer for the SSH runtime."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.common.secrets import encrypt_secret
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from . import provider
from .models import SSHExecution, SSHProfile
from .schemas import SSHProfileResponse, SSHProfileUpsert


class SSHService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def list_profiles(self, actor: User, project_id: uuid.UUID) -> list[SSHProfileResponse]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        result = await self.db.execute(
            select(SSHProfile)
            .where(SSHProfile.project_id == project_id)
            .order_by(SSHProfile.created_at.asc())
        )
        return [self._response(item) for item in result.scalars().all()]

    async def save_profile(
        self, actor: User, project_id: uuid.UUID, payload: SSHProfileUpsert
    ) -> SSHProfileResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        profile: SSHProfile | None = None
        if payload.id:
            profile = await self._get(project_id, payload.id)
        credentials = None
        if payload.secret:
            credentials = encrypt_secret(
                json.dumps(
                    {"secret": payload.secret, "key_passphrase": payload.key_passphrase},
                    ensure_ascii=False,
                )
            )
        if profile is None:
            assert credentials is not None
            profile = SSHProfile(
                project_id=project_id,
                created_by=actor.id,
                encrypted_credentials=credentials,
            )
            self.db.add(profile)
        elif credentials is not None:
            profile.encrypted_credentials = credentials
        profile.name = payload.name.strip()
        profile.host = payload.host.strip()
        profile.port = payload.port
        profile.username = payload.username.strip()
        profile.auth_type = payload.auth_type
        profile.known_hosts = payload.known_hosts.strip()
        profile.default_workdir = payload.default_workdir.strip()
        profile.last_verified_at = None
        await self.db.commit()
        await self.db.refresh(profile)
        return self._response(profile)

    async def delete_profile(
        self, actor: User, project_id: uuid.UUID, profile_id: uuid.UUID
    ) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        profile = await self._get(project_id, profile_id)
        await self.db.delete(profile)
        await self.db.commit()

    async def test(self, actor: User, project_id: uuid.UUID, profile_id: uuid.UUID) -> dict:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        profile = await self._get(project_id, profile_id)
        result = await provider.test_connection(profile)
        profile.last_verified_at = datetime.now(tz=UTC)
        await self.db.commit()
        return result

    async def tree(self, actor: User, project_id: uuid.UUID, profile_id: uuid.UUID) -> dict:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await provider.build_tree(await self._get(project_id, profile_id))

    async def read(
        self, actor: User, project_id: uuid.UUID, profile_id: uuid.UUID, path: str
    ) -> dict:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await provider.read_file(await self._get(project_id, profile_id), path)

    async def write(
        self,
        actor: User,
        project_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        path: str,
        content: str,
        base_sha: str | None,
    ) -> dict:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        return await provider.write_file(
            await self._get(project_id, profile_id), path, content, base_sha
        )

    async def execute(
        self,
        actor: User,
        project_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        argv: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> dict:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        profile = await self._get(project_id, profile_id)
        audit = SSHExecution(
            project_id=project_id,
            profile_id=profile.id,
            user_id=actor.id,
            argv_json=argv,
            workdir=cwd,
            status="running",
        )
        self.db.add(audit)
        await self.db.commit()
        try:
            result = await provider.run_command(profile, argv, cwd, timeout_seconds)
            audit.exit_code = result["exit_code"]
            audit.duration_ms = result["duration_ms"]
            audit.status = "timed_out" if result["timed_out"] else "completed"
            return result
        except Exception as exc:
            audit.status = "failed"
            audit.error = str(exc)[:2000]
            raise
        finally:
            await self.db.commit()

    async def _get(self, project_id: uuid.UUID, profile_id: uuid.UUID) -> SSHProfile:
        profile = await self.db.get(SSHProfile, profile_id)
        if profile is None or profile.project_id != project_id:
            raise NotFoundError("SSH profile not found.")
        return profile

    @staticmethod
    def _response(profile: SSHProfile) -> SSHProfileResponse:
        return SSHProfileResponse(
            id=profile.id,
            project_id=profile.project_id,
            name=profile.name,
            host=profile.host,
            port=profile.port,
            username=profile.username,
            auth_type=profile.auth_type,
            credential_masked="••••••••",
            default_workdir=profile.default_workdir,
            last_verified_at=profile.last_verified_at,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
