"""Organization endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    AddOrganizationMemberRequest,
    CreateOrganizationRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationWithRole,
)
from .service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationWithRole])
async def list_organizations(user: CurrentUser, db: DbSession) -> list[OrganizationWithRole]:
    pairs = await OrganizationService(db).list_for_user(user)
    return [
        OrganizationWithRole(id=org.id, name=org.name, slug=org.slug, plan=org.plan, role=role)
        for org, role in pairs
    ]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_organization(
    payload: CreateOrganizationRequest, user: CurrentUser, db: DbSession
) -> OrganizationResponse:
    org = await OrganizationService(db).create_organization(user, payload.name)
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrganizationResponse:
    org = await OrganizationService(db).get_organization(user, org_id)
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}/members", response_model=list[OrganizationMemberResponse])
async def list_members(
    org_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[OrganizationMemberResponse]:
    members = await OrganizationService(db).list_members(user, org_id)
    return [
        OrganizationMemberResponse(
            user_id=member.id, email=member.email, display_name=member.display_name, role=role
        )
        for member, role in members
    ]


@router.post(
    "/{org_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def add_member(
    org_id: uuid.UUID,
    payload: AddOrganizationMemberRequest,
    user: CurrentUser,
    db: DbSession,
) -> OrganizationMemberResponse:
    member, role = await OrganizationService(db).add_member(
        user, org_id, email=payload.email, role=payload.role
    )
    return OrganizationMemberResponse(
        user_id=member.id, email=member.email, display_name=member.display_name, role=role
    )
