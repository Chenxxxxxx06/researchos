"""Model aggregator.

Importing this module registers every ORM model on ``Base.metadata`` so that
Alembic (and any metadata-create path) can see the full schema. Import this
module wherever the complete metadata is required.
"""

from __future__ import annotations

from researchos.agents.models import AgentRun, AgentRunEvent, ToolCall
from researchos.coding_chat.models import ChatMessage, ChatSession
from researchos.common.base import Base
from researchos.documents.models import (
    DocumentFile,
    DocumentFileRevision,
    DocumentSuggestion,
    LatexCompileJob,
    LatexProject,
)
from researchos.experiments.models import (
    Experiment,
    ExperimentArtifact,
    ExperimentIngestToken,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)
from researchos.figures.models import Figure, FigureAsset, ResultAnchor
from researchos.identity.models import User
from researchos.llm_config.models import LLMProviderConfig
from researchos.organizations.models import Organization, OrganizationMembership
from researchos.patches.models import PatchFile, PatchHunk, PatchProposal
from researchos.preferences.models import UserPreference
from researchos.projects.models import Project, ProjectMembership
from researchos.research.models import Idea, Paper, PaperSection, ResearchCritique, ResearchFeedPref
from researchos.skills.models import Skill, SkillInstallation, SkillVersion

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrganizationMembership",
    "Project",
    "ProjectMembership",
    "Paper",
    "PaperSection",
    "ResearchFeedPref",
    "Idea",
    "ResearchCritique",
    "AgentRun",
    "ToolCall",
    "AgentRunEvent",
    "ChatSession",
    "ChatMessage",
    "PatchProposal",
    "PatchFile",
    "PatchHunk",
    "Experiment",
    "ExperimentRun",
    "ExperimentMetric",
    "ExperimentLog",
    "ExperimentArtifact",
    "ExperimentIngestToken",
    "ResultAnchor",
    "Figure",
    "FigureAsset",
    "UserPreference",
    "LatexProject",
    "DocumentFile",
    "DocumentFileRevision",
    "DocumentSuggestion",
    "LatexCompileJob",
    "Skill",
    "SkillVersion",
    "SkillInstallation",
    "LLMProviderConfig",
]
