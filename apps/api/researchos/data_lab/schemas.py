"""Data Lab API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasetColumn(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    type: Literal["text", "integer", "real", "boolean"] = "text"


class CreateDatasetSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20_000)
    columns: list[DatasetColumn] = Field(min_length=1, max_length=200)
    rows: list[dict] = Field(default_factory=list, max_length=5_000)

    @model_validator(mode="after")
    def validate_rows(self):
        names = [column.name for column in self.columns]
        if len(set(names)) != len(names):
            raise ValueError("Dataset column names must be unique.")
        allowed = set(names)
        if any(not set(row).issubset(allowed) for row in self.rows):
            raise ValueError("Dataset rows contain undeclared columns.")
        return self


class DatasetSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    columns_json: list
    rows_json: list
    created_by: uuid.UUID
    created_at: datetime


class RunSqlQuestionRequest(BaseModel):
    dataset_source_id: uuid.UUID
    question: str = Field(min_length=2, max_length=20_000)


class SqlQueryResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    dataset_source_id: uuid.UUID
    agent_run_id: uuid.UUID
    question: str
    sql: str
    explanation: str
    columns_json: list
    rows_json: list
    row_count: int
    created_at: datetime
