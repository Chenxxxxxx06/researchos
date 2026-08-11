"""Model aggregator.

Importing this module registers every ORM model on ``Base.metadata`` so that
Alembic (and any metadata-create path) can see the full schema. Import this
module wherever the complete metadata is required.
"""

from __future__ import annotations

from researchos.agents.models import AgentRun, AgentRunEvent, ToolCall
from researchos.citations.models import MissionCitationAudit
from researchos.coding_chat.models import ChatMessage, ChatSession
from researchos.common.base import Base
from researchos.data_lab.models import DatasetSource, SqlQueryResult
from researchos.documents.models import (
    DocumentFile,
    DocumentFileRevision,
    DocumentSuggestion,
    LatexCompileJob,
    LatexProject,
)
from researchos.experiment_plans.models import ExperimentPlan, ExperimentPlanVersion
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
from researchos.inbox.models import ResearchInboxItem
from researchos.knowledge.models import (
    MissionPaper,
    MissionTopicCluster,
    PaperChunk,
    ReadingCard,
    ReadingCardVersion,
    ReadingNote,
)
from researchos.llm_config.models import LLMProviderConfig
from researchos.missions.models import MissionEvent, MissionStep, ResearchMission
from researchos.organizations.models import Organization, OrganizationMembership
from researchos.patches.models import PatchFile, PatchHunk, PatchProposal
from researchos.preferences.models import UserPreference
from researchos.projects.models import Project, ProjectMembership
from researchos.research.models import Idea, Paper, PaperSection, ResearchCritique, ResearchFeedPref
from researchos.reviews.models import ReviewDocument, ReviewSection, ReviewVersion
from researchos.runtime.ssh.models import SSHExecution, SSHProfile
from researchos.skills.models import Skill, SkillInstallation, SkillVersion
from researchos.zotero.models import ZoteroConnection

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrganizationMembership",
    "Project",
    "ProjectMembership",
    "ResearchMission",
    "MissionStep",
    "MissionEvent",
    "MissionPaper",
    "MissionTopicCluster",
    "PaperChunk",
    "ReadingCard",
    "ReadingCardVersion",
    "ReadingNote",
    "Paper",
    "PaperSection",
    "ResearchFeedPref",
    "Idea",
    "ResearchCritique",
    "ReviewDocument",
    "ReviewSection",
    "ReviewVersion",
    "MissionCitationAudit",
    "DatasetSource",
    "SqlQueryResult",
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
    "ExperimentPlan",
    "ExperimentPlanVersion",
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
    "ZoteroConnection",
    "ResearchInboxItem",
    "SSHProfile",
    "SSHExecution",
]
