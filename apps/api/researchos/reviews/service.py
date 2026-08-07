"""Structured review outline, editing, citation checks, and versioning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.knowledge.models import MissionPaper, MissionTopicCluster
from researchos.missions.models import MissionEvent, ResearchMission
from researchos.projects.service import ProjectService
from researchos.research.models import Paper

from .models import ReviewDocument, ReviewSection, ReviewVersion
from .schemas import (
    GenerateReviewOutlineRequest,
    GenerateReviewSectionRequest,
    UpdateReviewSectionRequest,
)


class ReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _mission(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID, *, write: bool
    ) -> ResearchMission:
        await ProjectService(self.db).ensure_access(
            actor, project_id, ProjectRole.RESEARCHER if write else ProjectRole.VIEWER
        )
        mission = await self.db.get(ResearchMission, mission_id)
        if mission is None or mission.project_id != project_id:
            raise NotFoundError("Research mission not found.")
        return mission

    async def get(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> tuple[ReviewDocument, list[ReviewSection]]:
        await self._mission(actor, project_id, mission_id, write=False)
        review = await self.db.scalar(
            select(ReviewDocument).where(ReviewDocument.mission_id == mission_id)
        )
        if review is None:
            raise NotFoundError("Review document not found. Generate an outline first.")
        return review, await self._sections(review.id)

    async def generate_outline(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        payload: GenerateReviewOutlineRequest,
    ) -> tuple[ReviewDocument, list[ReviewSection]]:
        mission = await self._mission(actor, project_id, mission_id, write=True)
        review = await self.db.scalar(
            select(ReviewDocument).where(ReviewDocument.mission_id == mission_id)
        )
        if review is not None and not payload.regenerate:
            raise ConflictError(
                "A review outline already exists. Confirm regeneration to create a new version.",
                code="review_regeneration_confirmation_required",
            )
        clusters = list(
            (
                await self.db.execute(
                    select(MissionTopicCluster)
                    .where(MissionTopicCluster.mission_id == mission_id)
                    .order_by(MissionTopicCluster.position)
                )
            )
            .scalars()
            .all()
        )
        links = list(
            (
                await self.db.execute(
                    select(MissionPaper).where(MissionPaper.mission_id == mission_id)
                )
            )
            .scalars()
            .all()
        )
        if not links:
            raise ValidationError("Include papers before generating a review outline.")
        if review is None:
            review = ReviewDocument(
                project_id=project_id,
                mission_id=mission_id,
                title=f"{mission.topic}：结构化文献综述",
                status="outline",
                created_by=actor.id,
                updated_by=actor.id,
            )
            self.db.add(review)
            await self.db.flush()
        else:
            review.version += 1
            review.updated_by = actor.id
            review.status = "outline"
            await self.db.execute(delete(ReviewSection).where(ReviewSection.review_id == review.id))
        all_papers = [str(link.paper_id) for link in links]
        specs: list[tuple[str, str, str, list[str]]] = [
            (
                "introduction",
                "问题背景与综述范围",
                "界定研究问题、术语、纳入标准与本文组织方式。",
                all_papers[:20],
            ),
        ]
        for cluster in clusters:
            paper_ids = [str(link.paper_id) for link in links if link.cluster_id == cluster.id]
            specs.append(
                (
                    f"topic-{cluster.position + 1}",
                    cluster.name,
                    cluster.summary or "综合该主题下的方法、实验结论与局限。",
                    paper_ids,
                )
            )
        specs.extend(
            [
                (
                    "synthesis-gap",
                    "跨主题比较与研究空白",
                    "比较方法假设、数据、指标和矛盾结论，提出有证据边界的研究空白。",
                    all_papers,
                ),
                (
                    "conclusion",
                    "结论与实验设计衔接",
                    "总结可靠共识、仍有争议的问题，并说明实验方案的推导依据。",
                    all_papers[:20],
                ),
            ]
        )
        sections = []
        for position, (key, title, purpose, citations) in enumerate(specs):
            section = ReviewSection(
                project_id=project_id,
                mission_id=mission_id,
                review_id=review.id,
                section_key=key,
                position=position,
                title=title,
                purpose=purpose,
                body="",
                citations_json=citations,
                claims_json=[],
                status="outline",
                updated_by=actor.id,
            )
            self.db.add(section)
            sections.append(section)
        await self.db.flush()
        await self._snapshot(review, sections, actor.id, "outline")
        mission.last_activity_at = datetime.now(tz=UTC)
        mission.updated_by = actor.id
        self.db.add(
            MissionEvent(
                project_id=project_id,
                mission_id=mission_id,
                event_type="review.outline.generated",
                summary=f"生成包含 {len(sections)} 个章节的综述大纲 v{review.version}",
                step_kind=mission.current_step,
                payload_json={
                    "review_id": str(review.id),
                    "version": review.version,
                    "section_count": len(sections),
                },
                actor_id=actor.id,
            )
        )
        await self.db.commit()
        return review, sections

    async def update_section(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        section_id: uuid.UUID,
        payload: UpdateReviewSectionRequest,
    ) -> tuple[ReviewDocument, list[ReviewSection]]:
        await self._mission(actor, project_id, mission_id, write=True)
        section = await self.db.get(ReviewSection, section_id)
        if section is None or section.mission_id != mission_id:
            raise NotFoundError("Review section not found.")
        if section.version != payload.expected_version:
            raise ConflictError(
                "Review section changed elsewhere.", code="review_section_version_conflict"
            )
        review = await self.db.get(ReviewDocument, section.review_id)
        assert review is not None
        if payload.citations is not None:
            allowed = set(
                (
                    await self.db.execute(
                        select(MissionPaper.paper_id).where(MissionPaper.mission_id == mission_id)
                    )
                )
                .scalars()
                .all()
            )
            if not set(payload.citations).issubset(allowed):
                raise ValidationError(
                    "Every citation must reference a paper included in this mission."
                )
            section.citations_json = [str(item) for item in payload.citations]
        for field in ("title", "purpose", "body", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(section, field, value.strip() if isinstance(value, str) else value)
        if payload.claims is not None:
            section.claims_json = payload.claims
        section.version += 1
        section.updated_by = actor.id
        review.version += 1
        review.updated_by = actor.id
        review.status = "draft"
        sections = await self._sections(review.id)
        await self._snapshot(review, sections, actor.id, "human")
        await self.db.commit()
        return review, sections

    async def validate_section_generation(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        section_id: uuid.UUID,
        payload: GenerateReviewSectionRequest,
    ) -> ReviewSection:
        await self._mission(actor, project_id, mission_id, write=True)
        section = await self.db.get(ReviewSection, section_id)
        if section is None or section.mission_id != mission_id:
            raise NotFoundError("Review section not found.")
        if section.version != payload.expected_version:
            raise ConflictError(
                "Review section changed elsewhere.", code="review_section_version_conflict"
            )
        if section.body.strip() and not payload.regenerate:
            raise ConflictError(
                "This section already has a draft. Confirm regeneration to replace it.",
                code="review_section_regeneration_confirmation_required",
            )
        if not section.citations_json:
            raise ValidationError(
                "Select at least one mission paper before generating this section."
            )
        return section

    async def versions(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[ReviewVersion]:
        review, _ = await self.get(actor, project_id, mission_id)
        return list(
            (
                await self.db.execute(
                    select(ReviewVersion)
                    .where(ReviewVersion.review_id == review.id)
                    .order_by(ReviewVersion.version.desc())
                )
            )
            .scalars()
            .all()
        )

    async def paper_titles(self, project_id: uuid.UUID, paper_ids: list[str]) -> dict[str, str]:
        ids = [uuid.UUID(item) for item in paper_ids]
        rows = (
            await self.db.execute(
                select(Paper.id, Paper.title).where(
                    Paper.project_id == project_id, Paper.id.in_(ids)
                )
            )
        ).all()
        return {str(paper_id): title for paper_id, title in rows}

    async def _sections(self, review_id: uuid.UUID) -> list[ReviewSection]:
        return list(
            (
                await self.db.execute(
                    select(ReviewSection)
                    .where(ReviewSection.review_id == review_id)
                    .order_by(ReviewSection.position)
                )
            )
            .scalars()
            .all()
        )

    async def _snapshot(
        self,
        review: ReviewDocument,
        sections: list[ReviewSection],
        actor_id: uuid.UUID,
        source_type: str,
        source_run_id: uuid.UUID | None = None,
    ) -> None:
        await self.db.flush()
        self.db.add(
            ReviewVersion(
                project_id=review.project_id,
                mission_id=review.mission_id,
                review_id=review.id,
                version=review.version,
                snapshot_json={
                    "title": review.title,
                    "status": review.status,
                    "sections": [
                        {
                            "id": str(section.id),
                            "key": section.section_key,
                            "title": section.title,
                            "purpose": section.purpose,
                            "body": section.body,
                            "citations": section.citations_json,
                            "claims": section.claims_json,
                            "status": section.status,
                            "version": section.version,
                        }
                        for section in sections
                    ],
                },
                source_type=source_type,
                source_run_id=source_run_id,
                created_by=actor_id,
            )
        )
        await self.db.flush()


def review_metrics(sections: list[ReviewSection]) -> tuple[float, int]:
    coverage = (
        0.0
        if not sections
        else 100.0 * sum(bool(section.citations_json) for section in sections) / len(sections)
    )
    unsupported = sum(
        1
        for section in sections
        for claim in section.claims_json
        if isinstance(claim, dict) and claim.get("evidence_status") != "grounded"
    )
    return round(coverage, 1), unsupported
