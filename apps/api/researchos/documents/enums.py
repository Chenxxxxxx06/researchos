"""Enumerations for the documents (LaTeX) context."""

from __future__ import annotations

from enum import StrEnum


class CompileStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SuggestionOp(StrEnum):
    REWRITE = "rewrite"
    EXPAND = "expand"
    CONDENSE = "condense"
    FIX_GRAMMAR = "fix_grammar"
    CONTINUE_WRITING = "continue_writing"
    CUSTOM = "custom"


class SuggestionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
