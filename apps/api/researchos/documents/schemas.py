"""LaTeX document DTOs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .enums import CompileStatus, SuggestionOp, SuggestionStatus

_PATH_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._ /-]*$")


def validate_document_path(path: str) -> str:
    """Reject traversal/absolute/backslash paths (POSIX-relative only)."""

    if "\x00" in path or "\\" in path:
        raise ValueError("path must be POSIX-relative without backslashes")
    if path.startswith("/"):
        raise ValueError("path must be relative")
    segments = path.split("/")
    if any(seg in {"", ".."} for seg in segments):
        raise ValueError("path must not contain empty or '..' segments")
    if not _PATH_RE.fullmatch(path):
        raise ValueError("path contains unsupported characters")
    return path


class CreateLatexProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class LatexProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    main_file_path: str
    created_at: datetime


class DocumentFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    content: str
    version: int
    updated_at: datetime


class DocumentFileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    version: int


class SaveFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(default="", max_length=2_000_000)
    # Compare-and-swap: when provided, the save fails with 409
    # ``document_version_conflict`` unless it matches the stored version.
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("path")
    @classmethod
    def _path_ok(cls, value: str) -> str:
        return validate_document_path(value)


class FileVersionRef(BaseModel):
    path: str
    version: int


class FileRevisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    updated_by: uuid.UUID | None
    created_at: datetime


# --- selection ops / suggestions ---------------------------------------------


class Position(BaseModel):
    line: int = Field(ge=1)
    col: int = Field(ge=1)


class TextRange(BaseModel):
    start: Position
    end: Position

    @model_validator(mode="after")
    def _ordered(self) -> TextRange:
        if (self.end.line, self.end.col) < (self.start.line, self.start.col):
            raise ValueError("range end must not precede range start")
        return self


class SelectionOpRequest(BaseModel):
    op: SuggestionOp
    path: str = Field(min_length=1, max_length=512)
    range: TextRange
    selection_text: str = Field(default="", max_length=20_000)
    expected_version: int | None = Field(default=None, ge=1)
    instruction: str | None = Field(default=None, max_length=2_000)

    @field_validator("path")
    @classmethod
    def _path_ok(cls, value: str) -> str:
        return validate_document_path(value)

    @model_validator(mode="after")
    def _selection_required(self) -> SelectionOpRequest:
        if self.op != SuggestionOp.CONTINUE_WRITING and not self.selection_text:
            raise ValueError("selection_text must be non-empty for this op")
        return self


class SelectionOpResponse(BaseModel):
    agent_run_id: uuid.UUID
    stream: str


class SuggestionSpan(BaseModel):
    kind: Literal["equal", "delete", "insert", "replace"]
    old: str
    new: str


class SuggestionResponse(BaseModel):
    id: uuid.UUID
    path: str
    op: SuggestionOp
    status: SuggestionStatus
    base_version: int
    range: TextRange
    old_text: str
    new_text: str
    rationale: str
    spans: list[SuggestionSpan]
    agent_run_id: uuid.UUID | None
    last_error: str | None
    created_at: datetime
    resolved_at: datetime | None


class AcceptSuggestionRequest(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)


class AcceptSuggestionResponse(BaseModel):
    suggestion: SuggestionResponse
    file: DocumentFileResponse


# --- anchors -----------------------------------------------------------------


class InsertAnchorRequest(BaseModel):
    macro_name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z]*$")
    target_path: str = Field(default="main.tex", min_length=1, max_length=512)
    expected_version: int | None = Field(default=None, ge=1)
    insert_at: Position | None = None

    @field_validator("target_path")
    @classmethod
    def _path_ok(cls, value: str) -> str:
        return validate_document_path(value)


class InsertAnchorResponse(BaseModel):
    snippet: str
    include_added: bool
    validated: bool
    files: list[FileVersionRef]


# --- citations ---------------------------------------------------------------


class CitationItem(BaseModel):
    paper_id: uuid.UUID
    title: str
    authors: list[str]
    year: int | None
    cite_key: str
    in_bib: bool


class CitationListResponse(BaseModel):
    items: list[CitationItem]
    total: int
    limit: int
    offset: int


class InsertCitationRequest(BaseModel):
    paper_id: uuid.UUID
    bib_path: str = Field(default="refs.bib", min_length=1, max_length=512)
    expected_bib_version: int | None = Field(default=None, ge=1)
    expected_main_version: int | None = Field(default=None, ge=1)

    @field_validator("bib_path")
    @classmethod
    def _path_ok(cls, value: str) -> str:
        return validate_document_path(value)


class InsertCitationResponse(BaseModel):
    cite_key: str
    snippet: str
    bib_file: FileVersionRef
    entry_added: bool
    bibliography_command_added: bool


# --- compile -----------------------------------------------------------------


class CompileDiagnostic(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    file: str
    line: int


class CompileJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    latex_project_id: uuid.UUID
    status: CompileStatus
    engine: str
    log: str | None
    preview: str | None
    preview_model: dict | None = Field(
        default=None, validation_alias=AliasChoices("preview_model_json", "preview_model")
    )
    diagnostics: list[CompileDiagnostic] = Field(
        default_factory=list, validation_alias=AliasChoices("diagnostics_json", "diagnostics")
    )
    error_summary: str | None
    created_at: datetime
    finished_at: datetime | None
