"""Model aggregator.

Importing this module registers every ORM model on ``Base.metadata`` so that
Alembic (and any metadata-create path) can see the full schema. Import this
module wherever the complete metadata is required.
"""

from __future__ import annotations

from researchos.agents.models import AgentRun, AgentRunEvent, ToolCall
from researchos.common.base import Base
from researchos.documents.models import DocumentFile, LatexCompileJob, LatexProject
from researchos.experiments.models import (
    Experiment,
    ExperimentArtifact,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)
from researchos.identity.models import User
from researchos.organizations.models import Organization, OrganizationMembership
from researchos.patches.models import PatchFile, PatchHunk, PatchProposal
from researchos.projects.models import Project, ProjectMembership
from researchos.research.models import Idea, Paper, ResearchCritique
from researchos.skills.models import Skill, SkillInstallation, SkillVersion

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrganizationMembership",
    "Project",
    "ProjectMembership",
    "Paper",
    "Idea",
    "ResearchCritique",
    "AgentRun",
    "ToolCall",
    "AgentRunEvent",
    "PatchProposal",
    "PatchFile",
    "PatchHunk",
    "Experiment",
    "ExperimentRun",
    "ExperimentMetric",
    "ExperimentLog",
    "ExperimentArtifact",
    "LatexProject",
    "DocumentFile",
    "LatexCompileJob",
    "Skill",
    "SkillVersion",
    "SkillInstallation",
]
