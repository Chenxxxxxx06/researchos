"""First-party skill catalog and idempotent seeding.

First-party skills are global (no project). Seeding is idempotent: a skill is
created only if its slug does not already exist.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import SkillVisibility
from .models import Skill, SkillVersion

FIRST_PARTY_SKILLS: list[dict] = [
    {
        "slug": "nature-writing",
        "name": "Nature Writing Skill",
        "category": "writing",
        "description": "Rewrites paper prose in a clear, high-impact Nature style.",
        "modules": ["paper"],
        "prompt_template": (
            "Rewrite the selected text in the concise, authoritative style of a "
            "Nature article. Preserve all factual claims and citations."
        ),
        "workflow": ["Analyze selection", "Rewrite for clarity", "Tighten claims"],
        "tool_permissions": [],
        "config_schema": {"tone": {"type": "string", "default": "formal"}},
    },
    {
        "slug": "cvpr-reviewer",
        "name": "CVPR Reviewer Skill",
        "category": "review",
        "description": "Simulates a CVPR-style reviewer: novelty, weaknesses, baselines.",
        "modules": ["research"],
        "prompt_template": (
            "Review the idea as a CVPR reviewer. Assess novelty, missing baselines, "
            "dataset concerns, and reproducibility. Cite only provided papers."
        ),
        "workflow": ["Restate claim", "Compare to related work", "List weaknesses"],
        "tool_permissions": ["paper.search", "library.list"],
        "config_schema": {"strictness": {"type": "string", "default": "high"}},
    },
    {
        "slug": "vlm-evaluation",
        "name": "VLM Evaluation Skill",
        "category": "evaluation",
        "description": "Plans evaluation for vision-language models with metrics and benchmarks.",
        "modules": ["research", "experiments"],
        "prompt_template": (
            "Propose an evaluation plan for a vision-language model: benchmarks, "
            "metrics, baselines, and ablations."
        ),
        "workflow": ["Select benchmarks", "Define metrics", "Plan ablations"],
        "tool_permissions": ["experiment.read"],
        "config_schema": {"benchmarks": {"type": "array", "default": []}},
    },
    {
        "slug": "experiment-analyst",
        "name": "Experiment Analysis Skill",
        "category": "analysis",
        "description": "Summarizes runs, detects instability, and recommends next runs.",
        "modules": ["experiments"],
        "prompt_template": (
            "Summarize the experiment run using only recorded metrics. Highlight the "
            "best and final values and suggest next experiments."
        ),
        "workflow": ["Read metrics", "Summarize", "Recommend next runs"],
        "tool_permissions": ["experiment.read"],
        "config_schema": {},
    },
    {
        "slug": "latex-polish",
        "name": "LaTeX Polish Skill",
        "category": "writing",
        "description": "Polishes LaTeX prose and fixes common style issues.",
        "modules": ["paper"],
        "prompt_template": (
            "Polish the selected LaTeX text for grammar and academic tone. Keep math "
            "and citations unchanged."
        ),
        "workflow": ["Detect issues", "Polish prose", "Preserve math"],
        "tool_permissions": [],
        "config_schema": {},
    },
]


async def seed_first_party(db: AsyncSession) -> int:
    """Insert any missing first-party skills. Returns the number created."""

    created = 0
    for spec in FIRST_PARTY_SKILLS:
        existing = await db.scalar(select(Skill).where(Skill.slug == spec["slug"]))
        if existing is not None:
            continue
        skill = Skill(
            slug=spec["slug"],
            name=spec["name"],
            description=spec["description"],
            author="researchos",
            category=spec["category"],
            visibility=SkillVisibility.FIRST_PARTY,
        )
        db.add(skill)
        await db.flush()
        manifest = {
            "slug": spec["slug"],
            "name": spec["name"],
            "version": "1.0.0",
            "description": spec["description"],
            "author": "researchos",
            "category": spec["category"],
            "modules": spec["modules"],
            "prompt_template": spec["prompt_template"],
            "workflow": spec["workflow"],
            "tool_permissions": spec["tool_permissions"],
            "config_schema": spec["config_schema"],
        }
        db.add(SkillVersion(skill_id=skill.id, version="1.0.0", manifest_json=manifest))
        created += 1
    if created:
        await db.commit()
    return created
