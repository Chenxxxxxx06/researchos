"""Project-scoped aggregation for the unified management center."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.roles import ProjectRole
from researchos.experiment_plans.models import ExperimentPlan
from researchos.identity.models import User
from researchos.knowledge.models import ReadingNote
from researchos.missions.models import ResearchMission
from researchos.organizations.models import Organization
from researchos.projects.models import Project, ProjectMembership
from researchos.projects.service import ProjectService
from researchos.research.models import Paper


class ManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def summary(self, actor: User, project_id: uuid.UUID) -> dict:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.VIEWER)
        project = await self.db.get(Project, project_id)
        assert project is not None
        organization = await self.db.get(Organization, project.organization_id)
        assert organization is not None
        member_rows = (
            await self.db.execute(
                select(ProjectMembership, User)
                .join(User, User.id == ProjectMembership.user_id)
                .where(ProjectMembership.project_id == project_id)
                .order_by(User.display_name)
            )
        ).all()
        papers = list(
            (
                await self.db.execute(
                    select(Paper)
                    .where(Paper.project_id == project_id)
                    .order_by(Paper.created_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        plan_rows = (
            await self.db.execute(
                select(ExperimentPlan, ResearchMission)
                .join(ResearchMission, ResearchMission.id == ExperimentPlan.mission_id)
                .where(ExperimentPlan.project_id == project_id)
                .order_by(ExperimentPlan.updated_at.desc())
                .limit(100)
            )
        ).all()
        note_rows = (
            await self.db.execute(
                select(ReadingNote, Paper)
                .join(Paper, Paper.id == ReadingNote.paper_id)
                .where(ReadingNote.project_id == project_id)
                .order_by(ReadingNote.updated_at.desc())
                .limit(100)
            )
        ).all()
        counts = {
            "researchers": len(member_rows),
            "papers": await self._count(Paper, project_id),
            "experiment_plans": await self._count(ExperimentPlan, project_id),
            "reading_notes": await self._count(ReadingNote, project_id),
            "missions": await self._count(ResearchMission, project_id),
        }
        return {
            "organization": {
                "id": str(organization.id),
                "name": organization.name,
                "slug": organization.slug,
                "plan": organization.plan,
            },
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "field": project.field,
                "status": project.status.value,
            },
            "researchers": [
                {
                    "membership_id": str(membership.id),
                    "user_id": str(user.id),
                    "display_name": user.display_name,
                    "email": user.email,
                    "role": membership.role.value,
                    "is_active": user.is_active,
                }
                for membership, user in member_rows
            ],
            "papers": [
                {
                    "id": str(paper.id),
                    "title": paper.title,
                    "source": paper.source,
                    "year": paper.published_at.year if paper.published_at else None,
                    "ingest_status": paper.ingest_status.value,
                    "doi": paper.doi,
                    "updated_at": paper.updated_at.isoformat(),
                }
                for paper in papers
            ],
            "experiment_plans": [
                {
                    "id": str(plan.id),
                    "mission_id": str(mission.id),
                    "mission_topic": mission.topic,
                    "title": plan.title,
                    "status": plan.status,
                    "version": plan.version,
                    "published_experiment_id": (
                        str(plan.published_experiment_id) if plan.published_experiment_id else None
                    ),
                    "updated_at": plan.updated_at.isoformat(),
                }
                for plan, mission in plan_rows
            ],
            "reading_notes": [
                {
                    "id": str(note.id),
                    "mission_id": str(note.mission_id) if note.mission_id else None,
                    "paper_id": str(paper.id),
                    "paper_title": paper.title,
                    "note_type": "section_note" if note.section_id else "paper_note",
                    "content": note.content,
                    "updated_at": note.updated_at.isoformat(),
                }
                for note, paper in note_rows
            ],
            "counts": counts,
        }

    async def _count(self, model, project_id: uuid.UUID) -> int:
        return int(
            await self.db.scalar(
                select(func.count()).select_from(model).where(model.project_id == project_id)
            )
            or 0
        )
