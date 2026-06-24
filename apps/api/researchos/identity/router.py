"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from researchos.common.cookies import (
    clear_auth_cookies,
    set_csrf_cookie,
    set_session_cookie,
)
from researchos.common.csrf import issue_csrf_token
from researchos.common.deps import (
    CurrentUser,
    DbSession,
    get_session_id,
    require_csrf,
)
from researchos.common.roles import OrgRole
from researchos.common.session import create_session, revoke_session
from researchos.organizations.service import OrganizationService

from .schemas import (
    LoginRequest,
    MeResponse,
    OrganizationSummary,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


async def _start_session(response: Response, user_id: str) -> None:
    session_id = await create_session(user_id)
    set_session_cookie(response, session_id)
    set_csrf_cookie(response, issue_csrf_token(session_id))


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: DbSession) -> RegisterResponse:
    user, organization = await AuthService(db).register(
        email=payload.email, password=payload.password, display_name=payload.display_name
    )
    await _start_session(response, str(user.id))
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        organization=OrganizationSummary(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            role=OrgRole.OWNER,
        ),
    )


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, db: DbSession) -> UserResponse:
    user = await AuthService(db).authenticate(email=payload.email, password=payload.password)
    await _start_session(response, str(user.id))
    return UserResponse.model_validate(user)


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
async def logout(request: Request, response: Response, user: CurrentUser) -> Response:
    session_id = get_session_id(request)
    if session_id:
        await revoke_session(session_id)
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(request: Request, response: Response, user: CurrentUser, db: DbSession) -> MeResponse:
    organizations = await OrganizationService(db).list_for_user(user)
    # Refresh the CSRF cookie so a returning client always has a valid token.
    session_id = getattr(request.state, "session_id", None) or get_session_id(request)
    if session_id:
        set_csrf_cookie(response, issue_csrf_token(session_id))
    return MeResponse(
        user=UserResponse.model_validate(user),
        organizations=[
            OrganizationSummary(id=org.id, name=org.name, slug=org.slug, role=role)
            for org, role in organizations
        ],
    )
