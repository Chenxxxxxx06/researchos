"""Skill marketplace and skill-builder business logic.

First-party skills are global; custom skills belong to a project. Skills carry a
manifest (modules, prompt template, workflow, tool permissions, config schema) —
never executable code. Installing/enabling and creating custom skills require
researcher+; reading requires viewer+.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .enums import SkillVisibility
from .manifest import SkillManifest, validate_manifest
from .models import Skill, SkillInstallation, SkillVersion
from .repository import InstallationRepository, SkillRepository
from .schemas import (
    CustomSkillRequest,
    InstalledSkillResponse,
    SkillCatalogItem,
    SkillDetailResponse,
)


class SkillService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.skills = SkillRepository(db)
        self.installations = InstallationRepository(db)
        self.projects = ProjectService(db)

    @staticmethod
    def _manifest(version: SkillVersion | None) -> dict:
        return version.manifest_json if version else {}

    async def list_catalog(self, actor: User, project_id: uuid.UUID) -> list[SkillCatalogItem]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        skills = await self.skills.list_catalog(project_id)
        installs = {i.skill_id: i for i in await self.installations.list_for_project(project_id)}
        items: list[SkillCatalogItem] = []
        for skill in skills:
            manifest = self._manifest(await self.skills.latest_version(skill.id))
            inst = installs.get(skill.id)
            items.append(
                SkillCatalogItem(
                    slug=skill.slug,
                    name=skill.name,
                    description=skill.description,
                    author=skill.author,
                    category=skill.category,
                    visibility=skill.visibility,
                    modules=list(manifest.get("modules", [])),
                    installed=inst is not None,
                    enabled=bool(inst.enabled) if inst else False,
                )
            )
        return items

    async def _require_skill(self, project_id: uuid.UUID, slug: str) -> Skill:
        skill = await self.skills.get_by_slug(slug)
        if skill is None or (
            skill.visibility == SkillVisibility.CUSTOM and skill.project_id != project_id
        ):
            raise NotFoundError("Skill not found.")
        return skill

    async def get_skill(self, actor: User, project_id: uuid.UUID, slug: str) -> SkillDetailResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        skill = await self._require_skill(project_id, slug)
        version = await self.skills.latest_version(skill.id)
        manifest = self._manifest(version)
        inst = await self.installations.get(project_id, skill.id)
        return SkillDetailResponse(
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            author=skill.author,
            category=skill.category,
            visibility=skill.visibility,
            version=version.version if version else "1.0.0",
            modules=list(manifest.get("modules", [])),
            prompt_template=str(manifest.get("prompt_template", "")),
            workflow=list(manifest.get("workflow", [])),
            tool_permissions=list(manifest.get("tool_permissions", [])),
            config_schema=dict(manifest.get("config_schema", {})),
            installed=inst is not None,
            enabled=bool(inst.enabled) if inst else False,
        )

    async def install(self, actor: User, project_id: uuid.UUID, slug: str) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        skill = await self._require_skill(project_id, slug)
        version = await self.skills.latest_version(skill.id)
        if version is None:
            raise ValidationError("Skill has no published version.")
        inst = await self.installations.get(project_id, skill.id)
        if inst is None:
            await self.installations.add(
                SkillInstallation(
                    project_id=project_id,
                    skill_id=skill.id,
                    skill_version_id=version.id,
                    enabled=True,
                    installed_by=actor.id,
                )
            )
        else:
            inst.enabled = True
            inst.skill_version_id = version.id
        await self.db.commit()

    async def toggle(self, actor: User, project_id: uuid.UUID, slug: str, *, enabled: bool) -> None:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        skill = await self._require_skill(project_id, slug)
        inst = await self.installations.get(project_id, skill.id)
        if inst is None:
            raise NotFoundError("Skill is not installed.")
        inst.enabled = enabled
        await self.db.commit()

    async def list_installed(
        self, actor: User, project_id: uuid.UUID
    ) -> list[InstalledSkillResponse]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        out: list[InstalledSkillResponse] = []
        for inst in await self.installations.list_for_project(project_id):
            skill = await self.db.get(Skill, inst.skill_id)
            version = await self.db.get(SkillVersion, inst.skill_version_id)
            if skill is None:
                continue
            out.append(
                InstalledSkillResponse(
                    slug=skill.slug,
                    name=skill.name,
                    version=version.version if version else "1.0.0",
                    enabled=inst.enabled,
                )
            )
        return out

    # --- skill builder -------------------------------------------------------
    def validate(self, payload: CustomSkillRequest) -> list[str]:
        manifest = SkillManifest(**payload.model_dump())
        return validate_manifest(manifest)

    async def create_custom(
        self, actor: User, project_id: uuid.UUID, payload: CustomSkillRequest
    ) -> SkillDetailResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        errors = self.validate(payload)
        if errors:
            raise ValidationError("; ".join(errors))
        if await self.skills.get_by_slug(payload.slug) is not None:
            raise ConflictError("A skill with this slug already exists.")
        skill = await self.skills.add_skill(
            Skill(
                slug=payload.slug,
                name=payload.name,
                description=payload.description,
                author=actor.display_name,
                category=payload.category,
                visibility=SkillVisibility.CUSTOM,
                project_id=project_id,
                created_by=actor.id,
            )
        )
        await self.skills.add_version(
            SkillVersion(
                skill_id=skill.id,
                version=payload.version,
                manifest_json=self._to_manifest(payload),
            )
        )
        await self.db.commit()
        return await self.get_skill(actor, project_id, payload.slug)

    async def update_custom(
        self, actor: User, project_id: uuid.UUID, slug: str, payload: CustomSkillRequest
    ) -> SkillDetailResponse:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        skill = await self._require_skill(project_id, slug)
        if skill.visibility != SkillVisibility.CUSTOM:
            raise ValidationError("Only custom skills can be edited.")
        errors = self.validate(payload)
        if errors:
            raise ValidationError("; ".join(errors))
        skill.name = payload.name
        skill.description = payload.description
        skill.category = payload.category
        version = await self.skills.version_by_value(skill.id, payload.version)
        if version is None:
            await self.skills.add_version(
                SkillVersion(
                    skill_id=skill.id,
                    version=payload.version,
                    manifest_json=self._to_manifest(payload),
                )
            )
        else:
            version.manifest_json = self._to_manifest(payload)
        await self.db.commit()
        return await self.get_skill(actor, project_id, slug)

    @staticmethod
    def _to_manifest(payload: CustomSkillRequest) -> dict:
        data = payload.model_dump()
        data["author"] = "custom"
        return data
