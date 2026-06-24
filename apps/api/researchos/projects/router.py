"""Project endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .schemas import (
    AddProjectMemberRequest,
    CreateProjectRequest,
    ProjectMemberResponse,
    ProjectResponse,
    UpdateProjectMemberRequest,
    UpdateProjectRequest,
)
from .service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectResponse])
async def list_projects(
    user: CurrentUser,
    db: DbSession,
    organization_id: uuid.UUID = Query(...),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[ProjectResponse]:
    page = await ProjectService(db).list_projects(
        user,
        organization_id=organization_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return Page[ProjectResponse](
        items=[ProjectResponse.model_validate(p) for p in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_project(
    payload: CreateProjectRequest, user: CurrentUser, db: DbSession
) -> ProjectResponse:
    project = await ProjectService(db).create_project(
        user,
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
        field=payload.field,
    )
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ProjectResponse:
    project = await ProjectService(db).get_project(user, project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, dependencies=[Depends(require_csrf)])
async def update_project(
    project_id: uuid.UUID, payload: UpdateProjectRequest, user: CurrentUser, db: DbSession
) -> ProjectResponse:
    project = await ProjectService(db).update_project(
        user,
        project_id,
        name=payload.name,
        description=payload.description,
        field=payload.field,
    )
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}", response_model=ProjectResponse, dependencies=[Depends(require_csrf)]
)
async def archive_project(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ProjectResponse:
    project = await ProjectService(db).archive_project(user, project_id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ProjectMemberResponse]:
    members = await ProjectService(db).list_members(user, project_id)
    return [
        ProjectMemberResponse(
            user_id=member.id, email=member.email, display_name=member.display_name, role=role
        )
        for member, role in members
    ]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def add_project_member(
    project_id: uuid.UUID,
    payload: AddProjectMemberRequest,
    user: CurrentUser,
    db: DbSession,
) -> ProjectMemberResponse:
    member, role = await ProjectService(db).add_member(
        user, project_id, email=payload.email, role=payload.role
    )
    return ProjectMemberResponse(
        user_id=member.id, email=member.email, display_name=member.display_name, role=role
    )


@router.patch(
    "/{project_id}/members/{target_user_id}",
    response_model=ProjectMemberResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_project_member(
    project_id: uuid.UUID,
    target_user_id: uuid.UUID,
    payload: UpdateProjectMemberRequest,
    user: CurrentUser,
    db: DbSession,
) -> ProjectMemberResponse:
    member, role = await ProjectService(db).update_member_role(
        user, project_id, target_user_id, payload.role
    )
    return ProjectMemberResponse(
        user_id=member.id, email=member.email, display_name=member.display_name, role=role
    )


@router.delete(
    "/{project_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def remove_project_member(
    project_id: uuid.UUID, target_user_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await ProjectService(db).remove_member(user, project_id, target_user_id)
