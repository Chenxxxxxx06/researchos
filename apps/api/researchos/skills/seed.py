# ruff: noqa: E501
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
        "slug": "research-mentor",
        "name": "Research Mentor",
        "category": "mentoring",
        "description": (
            "Turns project evidence and experiment state into a prioritized, "
            "falsifiable next-step plan without inventing results."
        ),
        "modules": ["research"],
        "prompt_template": (
            "Act as a demanding but constructive research mentor. Separate OBSERVED FACTS, "
            "INTERPRETATIONS, RISKS, and NEXT ACTIONS. Audit whether the current experiment "
            "can falsify the central hypothesis; identify the smallest decisive next run; "
            "require baselines, controls, ablations, uncertainty, reproducibility metadata, "
            "and stop criteria. Never invent a metric, result, citation, run, or file. Mark "
            "missing evidence explicitly and rank actions by information gain and cost."
        ),
        "workflow": [
            "Reconstruct the claim-evidence chain",
            "Challenge confounds and missing controls",
            "Select the smallest decisive next experiment",
            "Define success, failure, and stop criteria",
            "Produce an ordered mentor checklist",
        ],
        "tool_permissions": ["paper.search", "library.list"],
        "config_schema": {},
    },
    {
        "slug": "reviewer-challenger",
        "name": "Reviewer Challenger",
        "category": "review",
        "description": (
            "Performs evidence-bound simulated peer review and converts weaknesses into a "
            "prioritized revision plan."
        ),
        "modules": ["research"],
        "prompt_template": (
            "Act as an independent Reviewer-Challenger. Verify claims against only the supplied "
            "manuscript and project evidence. Label unsupported claims [EVIDENCE GAP], distinguish "
            "fatal validity threats from presentational improvements, and issue at least two "
            "specific depth challenges. Review novelty, soundness, experimental sufficiency, "
            "statistics, reproducibility, clarity, ethics, and limitations. A simulated score "
            "must be presented as advice, never as a prediction of acceptance."
        ),
        "workflow": [
            "Desk and scope check",
            "Claim-to-evidence audit",
            "Independent strengths and weaknesses",
            "Depth challenges",
            "Prioritized revision plan",
        ],
        "tool_permissions": ["paper.search", "library.list"],
        "config_schema": {},
    },
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
    {
        "slug": "evidence-ranked-ideas",
        "name": "Evidence-ranked Ideas",
        "category": "ideation",
        "description": "Ranks ten falsifiable directions from paper ideas, benchmarks, code, and ablations.",
        "modules": ["research"],
        "prompt_template": (
            "Rank no more than ten directions. Score source evidence, cross-paper support, benchmark "
            "credibility, reported ablations, code availability, cost, and novelty risk. Keep inferred "
            "directions separate from reported paper conclusions. Define a small-batch pilot for each."
        ),
        "workflow": [
            "Aggregate tuple evidence",
            "Score directions",
            "Design pilot",
            "Return Top 10",
        ],
        "tool_permissions": ["knowledge.rag_search"],
        "config_schema": {"top_k": {"type": "integer", "default": 10}},
    },
    {
        "slug": "publication-flowchart",
        "name": "Publication Flowchart",
        "category": "figure",
        "description": "Creates a verified academic Mermaid method flow with correct arrow semantics.",
        "modules": ["paper"],
        "prompt_template": (
            "Generate a left-to-right Mermaid flowchart with semantic node ids, restrained colors, "
            "print-readable labels, and no arrow crossings. Every node and arrow must correspond to "
            "the supplied method or experiment artifact. Never add an unverified module. Return raw "
            "Mermaid without markdown fences and self-check every arrow source and target."
        ),
        "workflow": [
            "Map real modules",
            "Lay out left to right",
            "Verify every arrow",
            "Run safety preflight",
        ],
        "tool_permissions": [],
        "config_schema": {"direction": {"type": "string", "default": "LR"}},
    },
    {
        "slug": "paper-figure-table",
        "name": "Paper Figure and Table",
        "category": "figure",
        "description": "Builds FigureSpecs, LaTeX tables, captions, and provenance from recorded metrics.",
        "modules": ["paper", "experiments"],
        "prompt_template": (
            "Use only recorded ExperimentRun metrics. Prefer direct comparison bars for final benchmark "
            "scores, lines for trajectories, and explicit ablation tables. Use colorblind-safe styles, "
            "state direction and units, link every series to a run id, and never transcribe a number by guess."
        ),
        "workflow": [
            "Select evidence",
            "Choose chart grammar",
            "Generate FigureSpec",
            "Audit table values",
            "Write caption",
        ],
        "tool_permissions": ["experiment.read"],
        "config_schema": {"style": {"type": "string", "default": "clean-serif"}},
    },
    {
        "slug": "long-run-progress-controller",
        "name": "Long-run Progress Controller",
        "category": "orchestration",
        "description": "Monitors leases, runs, blockers, progress, and evidence-based stop conditions.",
        "modules": ["experiments"],
        "prompt_template": (
            "Report deterministic task completion, active leases and runs, failed receipts, current "
            "blockers, and the smallest next action. Never estimate ETA without completed-task timing. "
            "Pause on missing credentials, paid compute, integrity failure, repeated crash, or no progress."
        ),
        "workflow": ["Fold task events", "Check heartbeats", "Report progress", "Apply stop rules"],
        "tool_permissions": ["experiment.read"],
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
