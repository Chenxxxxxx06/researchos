"""Role and status enumerations shared by models, services, and schemas.

Role ladders are expressed via ``level`` so the service layer can compare
"actor role >= required role" without hard-coding comparisons.
"""

from __future__ import annotations

from enum import StrEnum


class OrgRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"

    @property
    def level(self) -> int:
        return _ORG_LEVELS[self]


class ProjectRole(StrEnum):
    VIEWER = "viewer"
    RESEARCHER = "researcher"
    ADMIN = "admin"
    OWNER = "owner"

    @property
    def level(self) -> int:
        return _PROJECT_LEVELS[self]


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


_ORG_LEVELS: dict[OrgRole, int] = {
    OrgRole.MEMBER: 0,
    OrgRole.ADMIN: 1,
    OrgRole.OWNER: 2,
}

_PROJECT_LEVELS: dict[ProjectRole, int] = {
    ProjectRole.VIEWER: 0,
    ProjectRole.RESEARCHER: 1,
    ProjectRole.ADMIN: 2,
    ProjectRole.OWNER: 3,
}


def org_role_satisfies(actual: OrgRole, required: OrgRole) -> bool:
    return actual.level >= required.level


def project_role_satisfies(actual: ProjectRole, required: ProjectRole) -> bool:
    return actual.level >= required.level
