"""Idempotent demo-data seeder.

Run:  python -m researchos.seed.demo

Every step checks whether the target already exists before creating, so the
command is safe to run repeatedly — it never duplicates data or breaks
existing projects.
"""

# ruff: noqa: E501 -- demo corpus sentences are intentionally kept readable and searchable.

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime

import structlog

import researchos.models  # noqa: F401 -- register every FK target for ORM flushes

logger = structlog.get_logger(__name__)

DEMO_EMAIL = "demo@researchos.dev"
DEMO_PASSWORD = "demo-password-123"
DEMO_DISPLAY = "Demo User"
DEMO_PROJECT = "ResearchOS Demo"


async def _seed() -> None:
    from researchos.common.db import get_sessionmaker

    async with get_sessionmaker()() as db:
        # 1. Demo user (idempotent)
        from researchos.identity.repository import UserRepository
        from researchos.identity.service import AuthService

        users = UserRepository(db)
        user = await users.get_by_email(DEMO_EMAIL)
        if user is None:
            user, _organization = await AuthService(db).register(
                email=DEMO_EMAIL,
                password=DEMO_PASSWORD,
                display_name=DEMO_DISPLAY,
            )
            logger.info("seed: created demo user", email=DEMO_EMAIL)
        else:
            logger.info("seed: demo user exists")

        # 2. Personal organization (restart: always present from register)
        from researchos.organizations.repository import OrganizationMembershipRepository

        org_members = OrganizationMembershipRepository(db)
        orgs = await org_members.list_for_user(user.id)
        if not orgs:
            logger.error("seed: demo user has no organization — register first")
            return
        org, org_role = orgs[0]
        logger.info("seed: org", name=org.name, role=org_role.value)

        # 3. Demo project (idempotent by name within org)
        from researchos.projects.repository import (
            ProjectMembershipRepository,
            ProjectRepository,
        )

        projects = ProjectRepository(db)
        # List all active projects in this org.
        from sqlalchemy import select

        from researchos.common.roles import ProjectRole, ProjectStatus
        from researchos.projects.models import Project

        all_projects = await db.execute(
            select(Project).where(
                Project.organization_id == org.id,
                Project.status == ProjectStatus.ACTIVE,
            )
        )
        existing = [p for p in all_projects.scalars().all() if p.name == DEMO_PROJECT]
        if existing:
            project = existing[0]
            logger.info("seed: demo project exists", id=str(project.id))
        else:
            project = await projects.create(
                organization_id=org.id,
                name=DEMO_PROJECT,
                description="Demo project showcasing all ResearchOS MVP modules.",
                field="AI / Machine Learning",
                created_by=user.id,
            )
            await db.commit()
            await db.refresh(project)
            logger.info("seed: created demo project", id=str(project.id))

        pid = project.id
        project_members = ProjectMembershipRepository(db)
        if await project_members.get(pid, user.id) is None:
            await project_members.create(
                project_id=pid,
                user_id=user.id,
                role=ProjectRole.OWNER,
            )
            await db.commit()
            logger.info("seed: demo project owner membership created")

        # Keep a visible provider template in Settings without intercepting the
        # safe mock-provider fallback used by the zero-configuration demo.
        from researchos.llm_config.models import LLMProviderConfig

        demo_llm_config = await db.scalar(
            select(LLMProviderConfig).where(
                LLMProviderConfig.project_id == pid,
                LLMProviderConfig.name == "OpenAI template",
            )
        )
        if demo_llm_config is None:
            db.add(
                LLMProviderConfig(
                    project_id=pid,
                    name="OpenAI template",
                    provider_type="openai_compatible",
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini",
                    api_key="",
                    is_active=False,
                    description=(
                        "Optional provider template. Add your own API key and "
                        "activate it to replace the built-in mock provider."
                    ),
                )
            )
            await db.commit()
            logger.info("seed: demo LLM provider template created")

        # 4. Workspace files (idempotent via existing tree)
        from researchos.workspace import fs
        from researchos.workspace.fs import ensure_workspace

        ensure_workspace(pid)
        ws_root = fs.workspace_root_for(pid)
        ws_root.mkdir(parents=True, exist_ok=True)
        if not (ws_root / "README.md").exists():
            (ws_root / "README.md").write_text(
                "# ResearchOS Demo\n\nThis project showcases the complete MVP loop.\n",
                encoding="utf-8",
            )
            (ws_root / "src").mkdir(parents=True, exist_ok=True)
            (ws_root / "src" / "train.py").write_text(
                "def train():\n    print('training...')\n", encoding="utf-8"
            )
            (ws_root / "src" / "utils.py").write_text(
                "def add(a, b):\n    return a + b\n", encoding="utf-8"
            )
            logger.info("seed: workspace files created")
        else:
            logger.info("seed: workspace files exist")

        # 5. Paper import (idempotent via unique constraint)
        from researchos.research.models import Paper as PaperModel
        from researchos.research.repository import PaperRepository

        papers = PaperRepository(db)
        existing_paper = await papers.get_by_external(pid, "arxiv", "2401.01234")
        if existing_paper is None:
            await papers.create(
                PaperModel(
                    project_id=pid,
                    source="arxiv",
                    external_id="2401.01234",
                    title="Efficient Vision-Language Pretraining for Document Understanding",
                    abstract=(
                        "An efficient pretraining method for vision-language "
                        "models applied to document understanding tasks."
                    ),
                    authors_json=["Alice Researcher", "Bob Scientist"],
                    venue="arXiv",
                    url="http://arxiv.org/abs/2401.01234",
                    imported_by=user.id,
                )
            )
            await db.commit()
            logger.info("seed: paper imported")

        # 6. Ideas (idempotent by title)
        from sqlalchemy import select as sa_select

        from researchos.research.models import Idea

        existing_idea = await db.scalar(
            sa_select(Idea).where(
                Idea.project_id == pid, Idea.title == "Efficient VLM pretraining with curriculum"
            )
        )
        if existing_idea is None:
            db.add(
                Idea(
                    project_id=pid,
                    title="Efficient VLM pretraining with curriculum",
                    description="Use curriculum learning to speed up VLM pretraining.",
                    created_by=user.id,
                )
            )
            await db.commit()
            logger.info("seed: idea created")

        # 7. Experiments (idempotent by name)
        from researchos.experiments.enums import ExperimentRunStatus
        from researchos.experiments.models import (
            Experiment,
            ExperimentArtifact,
            ExperimentLog,
            ExperimentMetric,
            ExperimentRun,
        )

        async def _seed_experiment(name: str, desc: str, runs_specs: list[dict]) -> None:
            existing_exp = None
            for exp in all_exps_list:
                if exp.name == name:
                    existing_exp = exp
                    break
            if existing_exp is None:
                exp = Experiment(
                    id=uuid.uuid4(), project_id=pid, name=name, description=desc, created_by=user.id
                )
                db.add(exp)
                await db.flush()
            else:
                exp = existing_exp
            for rs in runs_specs:
                existing_run = None
                for r in all_runs_list:
                    if r.experiment_id == exp.id and r.name == rs["name"]:
                        existing_run = r
                        break
                if existing_run is None:
                    run = ExperimentRun(
                        id=uuid.uuid4(),
                        experiment_id=exp.id,
                        project_id=pid,
                        name=rs["name"],
                        status=ExperimentRunStatus(rs["status"]),
                        created_by=user.id,
                    )
                    db.add(run)
                    await db.flush()
                    for s in range(rs.get("steps", 10)):
                        v_loss = round(rs["loss_start"] * (rs.get("decay", 0.78) ** s) + 0.15, 4)
                        v_acc = round(min(0.97, rs["acc_start"] + s * 0.065), 4)
                        db.add(
                            ExperimentMetric(
                                run_id=run.id, project_id=pid, name="loss", step=s, value=v_loss
                            )
                        )
                        db.add(
                            ExperimentMetric(
                                run_id=run.id, project_id=pid, name="accuracy", step=s, value=v_acc
                            )
                        )
                    for log_msg in ["epoch 1/10 started", "checkpoint saved"]:
                        seq = rs.get("logs_seeded", 0) + 1
                        db.add(
                            ExperimentLog(
                                run_id=run.id,
                                project_id=pid,
                                seq=seq,
                                level="info",
                                message=log_msg,
                            )
                        )
                        rs["logs_seeded"] = seq
                    db.add(
                        ExperimentArtifact(
                            run_id=run.id,
                            project_id=pid,
                            name="model.ckpt",
                            artifact_type="checkpoint",
                            uri="s3://demo/model.ckpt",
                            size_bytes=104857600,
                        )
                    )

        all_exps_list = (
            (await db.execute(sa_select(Experiment).where(Experiment.project_id == pid)))
            .scalars()
            .all()
        )
        all_runs_list = (
            (await db.execute(sa_select(ExperimentRun).where(ExperimentRun.project_id == pid)))
            .scalars()
            .all()
        )

        await _seed_experiment(
            "VLM Pretraining",
            "Vision-language pretraining hyperparameter sweep",
            [
                {"name": "baseline", "status": "completed", "loss_start": 2.0, "acc_start": 0.30},
                {"name": "curriculum", "status": "completed", "loss_start": 1.8, "acc_start": 0.35},
                {
                    "name": "ablation-no-aug",
                    "status": "running",
                    "loss_start": 2.2,
                    "acc_start": 0.28,
                },
            ],
        )
        await _seed_experiment(
            "Ablation Study",
            "Component ablation experiments",
            [
                {"name": "full-model", "status": "completed", "loss_start": 1.9, "acc_start": 0.33},
            ],
        )
        await db.commit()
        logger.info("seed: experiments seeded")

        # 8. Paper (LaTeX project) — idempotent
        from researchos.documents.models import LatexProject

        existing_lp = (
            await db.execute(
                sa_select(LatexProject).where(
                    LatexProject.project_id == pid, LatexProject.name == "VLM Paper"
                )
            )
        ).scalar_one_or_none()
        if existing_lp is None:
            from researchos.documents.models import DocumentFile as DocFileModel
            from researchos.documents.repository import (
                DocumentFileRepository,
                LatexProjectRepository,
            )

            lp_repo = LatexProjectRepository(db)
            df_repo = DocumentFileRepository(db)
            lp = await lp_repo.add(
                LatexProject(project_id=pid, name="VLM Paper", created_by=user.id)
            )
            await df_repo.add(
                DocFileModel(
                    latex_project_id=lp.id,
                    path="main.tex",
                    content=r"""\documentclass{article}
\title{VLM Pretraining with Curriculum Learning}
\author{ResearchOS Demo}
\begin{document}
\maketitle
\section{Introduction}
Efficient vision-language pretraining is crucial for document understanding tasks.
\section{Method}
We propose a curriculum learning approach for VLM pretraining.
\section{Results}
Our experiments show consistent improvement over the baseline.
\end{document}""",
                    updated_by=user.id,
                )
            )
            await db.commit()
            logger.info("seed: latex project created")

        # 9. Skills install (idempotent)
        from researchos.skills.models import Skill as SkillModel
        from researchos.skills.models import SkillInstallation as SkillInstallationModel
        from researchos.skills.models import SkillVersion as SkillVersionModel
        from researchos.skills.repository import InstallationRepository

        installs = InstallationRepository(db)
        existing_installs = await installs.list_for_project(pid)
        installed_slugs = set()
        for inst in existing_installs:
            skill = await db.get(SkillModel, inst.skill_id)
            if skill:
                installed_slugs.add(skill.slug)
        target_slugs = {"nature-writing", "cvpr-reviewer", "experiment-analyst"}
        for slug in target_slugs - installed_slugs:
            skill = await db.scalar(sa_select(SkillModel).where(SkillModel.slug == slug))
            if skill is None:
                continue
            version = await db.scalar(
                sa_select(SkillVersionModel)
                .where(SkillVersionModel.skill_id == skill.id)
                .order_by(SkillVersionModel.created_at.desc())
            )
            if version is None:
                continue
            await installs.add(
                SkillInstallationModel(
                    project_id=pid,
                    skill_id=skill.id,
                    skill_version_id=version.id,
                    enabled=True,
                    installed_by=user.id,
                )
            )
        if target_slugs - installed_slugs:
            await db.commit()
            logger.info("seed: skills installed", slugs=list(target_slugs - installed_slugs))
        else:
            logger.info("seed: skills already installed")

        # 10. Complete teacher-requirement Mission demo (idempotent by topic).
        # This is intentionally richer than the legacy single-paper seed: it gives
        # the UI a stable literature → reading → review → experiment-plan story.
        from researchos.data_lab.models import DatasetSource
        from researchos.experiment_plans.models import ExperimentPlan
        from researchos.experiment_plans.service import record_plan_version
        from researchos.knowledge.indexing import index_paper_sections
        from researchos.knowledge.models import (
            MissionPaper,
            MissionTopicCluster,
            ReadingCard,
            ReadingNote,
        )
        from researchos.knowledge.service import record_card_version
        from researchos.missions.enums import (
            MISSION_STEP_ORDER,
            MissionStatus,
            MissionStepKind,
            MissionStepStatus,
        )
        from researchos.missions.models import MissionEvent, MissionStep, ResearchMission
        from researchos.research.enums import (
            PaperIngestStatus,
            PaperSectionKind,
        )
        from researchos.research.models import PaperSection
        from researchos.reviews.models import ReviewDocument, ReviewSection
        from researchos.reviews.service import ReviewService

        demo_topic = "低资源文档理解：从证据综述到可复现实验"
        demo_mission = await db.scalar(
            sa_select(ResearchMission).where(
                ResearchMission.project_id == pid,
                ResearchMission.topic == demo_topic,
            )
        )
        if demo_mission is None:
            paper_specs = [
                (
                    "demo-001",
                    "[DEMO] Layout-aware pretraining under limited annotation",
                    "layout encoder",
                    "A layout-aware encoder is evaluated under limited labels. The method combines token and bounding-box features.",
                    "Across three declared seeds, the layout-aware treatment improves macro-F1 over the text-only baseline while using the same training budget.",
                ),
                (
                    "demo-002",
                    "[DEMO] OCR noise robustness for document classifiers",
                    "robustness",
                    "The study introduces controlled OCR corruption and consistency training for document classification.",
                    "Consistency training reduces the score drop under medium OCR noise, but the benefit narrows at severe corruption.",
                ),
                (
                    "demo-003",
                    "[DEMO] Parameter-efficient adaptation of multimodal encoders",
                    "parameter efficiency",
                    "Adapters are inserted into a frozen multimodal encoder and compared with full fine-tuning.",
                    "Adapter tuning reaches a similar validation score with fewer trainable parameters; inference cost is unchanged.",
                ),
                (
                    "demo-004",
                    "[DEMO] Curriculum sampling for low-resource form understanding",
                    "training strategy",
                    "Examples are ordered from clean short forms to noisy long forms using a fixed curriculum schedule.",
                    "The curriculum shows faster early convergence, while final accuracy depends on the schedule and seed policy.",
                ),
                (
                    "demo-005",
                    "[DEMO] Cross-domain evaluation of invoice extraction",
                    "evaluation",
                    "Models trained on one invoice source are evaluated on held-out organizations without target-domain tuning.",
                    "All methods lose performance out of domain, exposing domain shift as a primary validity risk.",
                ),
                (
                    "demo-006",
                    "[DEMO] Synthetic augmentation for scarce document labels",
                    "data augmentation",
                    "Synthetic layouts and fields augment a small verified training set; synthetic-only training is excluded.",
                    "Mixed real and synthetic training improves recall, but gains disappear when synthetic noise is not controlled.",
                ),
                (
                    "demo-007",
                    "[DEMO] Calibration of confidence in document extraction",
                    "uncertainty",
                    "Temperature scaling and ensemble uncertainty are assessed on the same held-out split.",
                    "Calibration error improves after scaling without changing extraction accuracy, supporting separate calibration reporting.",
                ),
                (
                    "demo-008",
                    "[DEMO] Reproducible benchmarks for low-resource documents",
                    "reproducibility",
                    "The benchmark fixes splits, preprocessing, metric definitions, seeds, and environment capture.",
                    "Variance across seeds remains material, so the benchmark recommends reporting mean and standard deviation.",
                ),
            ]
            demo_papers: list[PaperModel] = []
            first_sections: dict[uuid.UUID, PaperSection] = {}
            for index, (external_id, title, category, method_text, result_text) in enumerate(
                paper_specs
            ):
                paper = await papers.get_by_external(pid, "demo", external_id)
                if paper is None:
                    paper = await papers.create(
                        PaperModel(
                            project_id=pid,
                            source="demo",
                            external_id=external_id,
                            title=title,
                            abstract=(
                                f"Demonstration literature record for {category}; it exists to "
                                "exercise the evidence workflow without claiming a real publication."
                            ),
                            authors_json=[f"Demo Author {index + 1}", "ResearchOS Team"],
                            venue="ResearchOS Demonstration Corpus",
                            url=f"https://example.invalid/researchos/{external_id}",
                            summary=f"A demo study about {category} in low-resource documents.",
                            primary_category="cs.CL",
                            ingest_status=PaperIngestStatus.SUCCEEDED,
                            ingested_at=datetime.now(tz=UTC),
                            metadata_json={"demo": True, "not_a_real_publication": True},
                            imported_by=user.id,
                        )
                    )
                existing_sections = list(
                    (
                        await db.execute(
                            sa_select(PaperSection)
                            .where(PaperSection.paper_id == paper.id)
                            .order_by(PaperSection.seq)
                        )
                    )
                    .scalars()
                    .all()
                )
                if not existing_sections:
                    method = PaperSection(
                        paper_id=paper.id,
                        seq=0,
                        level=1,
                        heading="Method",
                        body=method_text,
                        char_count=len(method_text),
                        kind=PaperSectionKind.METHOD,
                    )
                    result = PaperSection(
                        paper_id=paper.id,
                        seq=1,
                        level=1,
                        heading="Results and limitations",
                        body=result_text,
                        char_count=len(result_text),
                        kind=PaperSectionKind.RESULTS,
                    )
                    db.add_all([method, result])
                    await db.flush()
                    existing_sections = [method, result]
                first_sections[paper.id] = existing_sections[0]
                await index_paper_sections(db, paper)
                demo_papers.append(paper)

            now = datetime.now(tz=UTC)
            demo_mission = ResearchMission(
                project_id=pid,
                topic=demo_topic,
                objective="形成一份有证据的主题综述，并发布一套可复现的主实验方案。",
                field="Document AI / Low-resource learning",
                status=MissionStatus.ACTIVE,
                current_step=MissionStepKind.EXPERIMENT_PLAN,
                scope_json={
                    "year_from": 2020,
                    "minimum_papers": 8,
                    "include": ["low-resource", "document understanding", "reproducibility"],
                    "exclude": ["synthetic-only evidence"],
                },
                progress=80.0,
                last_activity_at=now,
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(demo_mission)
            await db.flush()
            for position, kind in enumerate(MISSION_STEP_ORDER):
                completed = kind != MissionStepKind.EXPERIMENT_PLAN
                db.add(
                    MissionStep(
                        mission_id=demo_mission.id,
                        project_id=pid,
                        step_kind=kind,
                        position=position,
                        status=(
                            MissionStepStatus.COMPLETED
                            if completed
                            else MissionStepStatus.NEEDS_REVIEW
                        ),
                        input_json={},
                        output_json={
                            "summary": (
                                "演示数据已人工复核" if completed else "结构化实验方案等待最终发布"
                            )
                        },
                        started_at=now,
                        completed_at=now if completed else None,
                        approved_by=user.id if completed else None,
                        approved_at=now if completed else None,
                    )
                )
            cluster_specs = [
                ("模型与训练策略", ["layout", "adapter", "curriculum"]),
                ("数据与稳健性", ["OCR", "domain shift", "augmentation"]),
                ("评价与复现", ["calibration", "seeds", "benchmark"]),
            ]
            clusters: list[MissionTopicCluster] = []
            for position, (name, keywords) in enumerate(cluster_specs):
                cluster = MissionTopicCluster(
                    project_id=pid,
                    mission_id=demo_mission.id,
                    name=name,
                    summary=f"演示主题簇：{name}。",
                    keywords_json=keywords,
                    algorithm="seeded-demo-v1",
                    status="reviewed",
                    position=position,
                    created_by=user.id,
                    updated_by=user.id,
                )
                db.add(cluster)
                clusters.append(cluster)
            await db.flush()
            for index, paper in enumerate(demo_papers):
                db.add(
                    MissionPaper(
                        project_id=pid,
                        mission_id=demo_mission.id,
                        paper_id=paper.id,
                        cluster_id=clusters[min(index // 3, 2)].id,
                        relevance_score=0.96 - index * 0.02,
                        inclusion_reason="满足演示 Mission 的主题与证据范围。",
                        included_by=user.id,
                    )
                )
                source = first_sections[paper.id]
                card = ReadingCard(
                    project_id=pid,
                    mission_id=demo_mission.id,
                    paper_id=paper.id,
                    summary=f"{paper.title} 的结构化演示阅读卡。",
                    research_question="该方法在低资源条件下如何影响效果与可复现性？",
                    method_flow_json=["固定数据切分", "运行对照与处理组", "跨种子报告指标"],
                    strengths_json=["方法和对照定义明确"],
                    limitations_json=["该记录属于产品演示语料，不是真实出版物"],
                    reproducibility_json=["固定代码、数据版本、种子与算力预算"],
                    claims_json=[
                        {
                            "text": source.body,
                            "section_id": str(source.id),
                            "section_seq": source.seq,
                            "heading": source.heading,
                            "quote": source.body,
                            "inference": False,
                            "evidence_status": "grounded",
                        }
                    ],
                    status="reviewed",
                    reviewed_at=now,
                    created_by=user.id,
                    updated_by=user.id,
                )
                db.add(card)
                await record_card_version(
                    db,
                    card,
                    actor_id=user.id,
                    source_type="seed_demo",
                    source_run_id=None,
                )
                if index < 3:
                    db.add(
                        ReadingNote(
                            project_id=pid,
                            mission_id=demo_mission.id,
                            paper_id=paper.id,
                            section_id=source.id,
                            quote=source.body,
                            content="演示笔记：该证据可用于综述比较与实验基线选择。",
                            tags_json=["demo", "baseline"],
                            created_by=user.id,
                            updated_by=user.id,
                        )
                    )

            review = ReviewDocument(
                project_id=pid,
                mission_id=demo_mission.id,
                title="低资源文档理解：结构化证据综述",
                status="draft",
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(review)
            await db.flush()
            review_sections: list[ReviewSection] = []
            for position, cluster in enumerate(clusters):
                linked = [
                    paper
                    for index, paper in enumerate(demo_papers)
                    if min(index // 3, 2) == position
                ]
                source = first_sections[linked[0].id]
                section = ReviewSection(
                    project_id=pid,
                    mission_id=demo_mission.id,
                    review_id=review.id,
                    section_key=f"topic-{position + 1}",
                    position=position,
                    title=cluster.name,
                    purpose=f"跨论文综合{cluster.name}的共识、差异与证据边界。",
                    body=(
                        f"演示综述段落：{cluster.name}需要在相同数据切分、预算和种子下比较。"
                        "当前文字明确标记为演示内容。"
                    ),
                    citations_json=[str(paper.id) for paper in linked],
                    claims_json=[
                        {
                            "text": source.body,
                            "paper_id": str(linked[0].id),
                            "paper_title": linked[0].title,
                            "section_id": str(source.id),
                            "section_seq": source.seq,
                            "heading": source.heading,
                            "quote": source.body,
                            "inference": False,
                            "evidence_status": "grounded",
                        }
                    ],
                    status="needs_review",
                    updated_by=user.id,
                )
                db.add(section)
                review_sections.append(section)
            await ReviewService(db)._snapshot(review, review_sections, user.id, "seed_demo")

            baseline_paper = demo_papers[0]
            baseline_source = first_sections[baseline_paper.id]
            plan = ExperimentPlan(
                project_id=pid,
                mission_id=demo_mission.id,
                title="低资源文档理解主实验（演示）",
                research_gap="现有演示证据缺少统一预算、切分和种子下的跨方法比较。",
                hypothesis="在相同预算下，布局感知处理组的 macro-F1 高于文本基线。",
                variables_json=[
                    {
                        "name": "layout-aware encoder",
                        "role": "independent",
                        "operational_definition": "是否启用布局编码器",
                        "levels_or_measurement": "off / on",
                    },
                    {
                        "name": "macro-F1",
                        "role": "dependent",
                        "operational_definition": "held-out test macro-F1",
                        "levels_or_measurement": "0–1",
                    },
                    {
                        "name": "training budget",
                        "role": "control",
                        "operational_definition": "每组相同 step 和硬件预算",
                        "levels_or_measurement": "fixed",
                    },
                ],
                baselines_json=[
                    {
                        "name": "text-only baseline",
                        "rationale": "任务内文献使用的主要对照。",
                        "source_paper_id": str(baseline_paper.id),
                        "evidence_section_id": str(baseline_source.id),
                        "evidence_quote": baseline_source.body,
                        "evidence_status": "grounded",
                    }
                ],
                datasets_json=[
                    {
                        "name": "Demo low-resource forms",
                        "split": "60/20/20，按组织分组避免泄漏",
                        "preprocessing": "仅在训练集拟合；测试集冻结",
                        "license_or_access": "演示合成数据",
                    }
                ],
                metrics_json=[
                    {"name": "macro_f1", "direction": "max", "primary": True, "unit": ""},
                    {
                        "name": "calibration_error",
                        "direction": "min",
                        "primary": False,
                        "unit": "",
                    },
                ],
                matrix_json=[
                    {
                        "name": "main comparison",
                        "factors": {"method": ["text-only", "layout-aware"]},
                        "repetitions": 3,
                        "seed_policy": "固定 11/22/33，所有组共用",
                        "compute_budget": "每组 3 GPU-hours（演示）",
                    }
                ],
                decision_rules_json=["仅当三次种子均值提高且方差未显著增大时支持假设。"],
                stop_conditions_json=["完成预注册矩阵后停止，不根据中间测试集结果追加运行。"],
                risks_json=[
                    {
                        "risk": "组织级数据泄漏",
                        "mitigation": "按组织分组切分并冻结测试集",
                        "severity": "high",
                    }
                ],
                reproducibility_json=["记录 git commit、数据版本、环境、完整配置与随机种子"],
                status="needs_review",
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(plan)
            await record_plan_version(db, plan, user.id, "seed_demo")
            db.add(
                DatasetSource(
                    project_id=pid,
                    name="Demo experiment metrics",
                    description="用于 SQL Data Lab 的可复现演示快照。",
                    columns_json=[
                        {"name": "method", "type": "text"},
                        {"name": "seed", "type": "integer"},
                        {"name": "macro_f1", "type": "real"},
                    ],
                    rows_json=[
                        {"method": method, "seed": seed, "macro_f1": score}
                        for method, values in {
                            "text_only": [0.68, 0.70, 0.69],
                            "layout_aware": [0.75, 0.77, 0.76],
                        }.items()
                        for seed, score in zip([11, 22, 33], values, strict=True)
                    ],
                    created_by=user.id,
                )
            )
            db.add(
                MissionEvent(
                    project_id=pid,
                    mission_id=demo_mission.id,
                    event_type="demo.full_chain.seeded",
                    summary="已生成 8 篇演示文献、3 个主题簇、阅读卡、综述与实验方案",
                    step_kind=MissionStepKind.EXPERIMENT_PLAN,
                    payload_json={"paper_count": 8, "cluster_count": 3},
                    actor_id=user.id,
                )
            )
            await db.commit()
            logger.info("seed: complete Mission demo created", mission_id=str(demo_mission.id))
        else:
            logger.info("seed: complete Mission demo exists", mission_id=str(demo_mission.id))

    logger.info("seed: DONE", project_id=str(pid))


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("seed_failed", error=str(exc), exc_info=exc)
        sys.exit(1)
