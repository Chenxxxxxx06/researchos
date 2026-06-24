"""Enumerations for patch proposals."""

from __future__ import annotations

from enum import StrEnum


class PatchStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    CONFLICT = "conflict"

    @property
    def is_terminal(self) -> bool:
        return self in {PatchStatus.APPLIED, PatchStatus.REJECTED}


class PatchChangeType(StrEnum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
