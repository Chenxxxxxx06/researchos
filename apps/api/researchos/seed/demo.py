"""Idempotent demo-data seeder.

Run:  python -m researchos.seed.demo

Every step checks whether the target already exists before creating, so the
command is safe to run repeatedly — it never duplicates data or breaks
existing projects.
"""

from __future__ import annotations

import asyncio
import sys

import structlog

logger = structlog.get_logger(__name__)

DEMO_EMAIL = "demo@researchos.dev"
DEMO_PASSWORD = "demo-password-123"
DEMO_DISPLAY = "Demo User"
DEMO_PROJECT = "ResearchOS Demo"


async def _seed() -> None:
    from researchos.common.db import get_sessionmaker

    async with get_sessionmaker()() as db:
        # 1. Demo user (idempotent)
        from researchos.common.security import hash_password
        from researchos.identity.repository import UserRepository

        users = UserRepository(db)
        user = await users.get_by_email(DEMO_EMAIL)
        if user is None:
            user = await users.create(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=DEMO_DISPLAY,
            )
            await db.commit()
            await db.refresh(user)
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
        from researchos.projects.repository import ProjectRepository

        projects = ProjectRepository(db)
        # List all active projects in this org.
        from sqlalchemy import select

        from researchos.common.roles import ProjectStatus
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

        def _seed_experiment(name: str, desc: str, runs_specs: list[dict]) -> None:
            existing_exp = None
            for exp in all_exps_list:
                if exp.name == name:
                    existing_exp = exp
                    break
            if existing_exp is None:
                exp = Experiment(project_id=pid, name=name, description=desc, created_by=user.id)
                db.add(exp)
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
                        experiment_id=exp.id,
                        project_id=pid,
                        name=rs["name"],
                        status=ExperimentRunStatus(rs["status"]),
                        created_by=user.id,
                    )
                    db.add(run)
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

        _seed_experiment(
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
        _seed_experiment(
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

    logger.info("seed: DONE", project_id=str(pid))


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("seed_failed", error=str(exc), exc_info=exc)
        sys.exit(1)
