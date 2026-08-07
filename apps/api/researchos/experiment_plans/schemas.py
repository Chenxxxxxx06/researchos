"""Experiment plan API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VariableItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: Literal["independent", "dependent", "control", "confounder"]
    operational_definition: str = Field(default="", max_length=10_000)
    levels_or_measurement: str = Field(default="", max_length=10_000)


class BaselineItem(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    rationale: str = Field(default="", max_length=10_000)
    source_paper_id: uuid.UUID | None = None
    evidence_section_id: uuid.UUID | None = None
    evidence_quote: str = Field(default="", max_length=3_000)
    evidence_status: Literal["grounded", "needs_evidence"] = "needs_evidence"


class DatasetItem(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    split: str = Field(default="", max_length=5_000)
    preprocessing: str = Field(default="", max_length=10_000)
    license_or_access: str = Field(default="", max_length=5_000)


class MetricItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    direction: Literal["min", "max"]
    primary: bool = False
    unit: str = Field(default="", max_length=100)


class MatrixItem(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    factors: dict = Field(default_factory=dict)
    repetitions: int = Field(default=1, ge=1, le=10_000)
    seed_policy: str = Field(default="", max_length=2_000)
    compute_budget: str = Field(default="", max_length=2_000)


class RiskItem(BaseModel):
    risk: str = Field(min_length=1, max_length=5_000)
    mitigation: str = Field(default="", max_length=5_000)
    severity: Literal["low", "medium", "high"] = "medium"


class UpsertExperimentPlanRequest(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=400)
    research_gap: str = Field(default="", max_length=50_000)
    hypothesis: str = Field(default="", max_length=50_000)
    variables: list[VariableItem] = Field(default_factory=list, max_length=200)
    baselines: list[BaselineItem] = Field(default_factory=list, max_length=200)
    datasets: list[DatasetItem] = Field(default_factory=list, max_length=100)
    metrics: list[MetricItem] = Field(default_factory=list, max_length=100)
    matrix: list[MatrixItem] = Field(default_factory=list, max_length=500)
    decision_rules: list[str] = Field(default_factory=list, max_length=100)
    stop_conditions: list[str] = Field(default_factory=list, max_length=100)
    risks: list[RiskItem] = Field(default_factory=list, max_length=100)
    reproducibility: list[str] = Field(default_factory=list, max_length=200)
    status: Literal["draft", "needs_review", "approved"] = "draft"


class GenerateExperimentPlanRequest(BaseModel):
    expected_version: int = Field(default=0, ge=0)
    regenerate: bool = False


class ExperimentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    title: str
    research_gap: str
    hypothesis: str
    variables_json: list
    baselines_json: list
    datasets_json: list
    metrics_json: list
    matrix_json: list
    decision_rules_json: list
    stop_conditions_json: list
    risks_json: list
    reproducibility_json: list
    status: str
    version: int
    generated_by_run_id: uuid.UUID | None
    published_experiment_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ExperimentPlanVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    plan_id: uuid.UUID
    version: int
    snapshot_json: dict
    source_type: str
    source_run_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


class PublishExperimentPlanResponse(BaseModel):
    plan: ExperimentPlanResponse
    experiment_id: uuid.UUID
