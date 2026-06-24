"""Shared FastAPI dependencies: current user and CSRF protection.

NOTE on layering: dependencies resolve *who* the caller is (authentication) and
enforce CSRF. Authorization (tenant isolation and role checks) lives in the
service layer, not here.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.csrf import validate_csrf_token
from researchos.common.db import get_session as get_db_session
from researchos.common.errors import AppError, UnauthorizedError
from researchos.common.session import read_session
from researchos.identity.models import User

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFError(AppError):
    code = "csrf_failed"
    http_status = 403
    message = "CSRF validation failed."


def get_session_id(request: Request) -> str | None:
    settings = get_settings()
    return request.cookies.get(settings.session_cookie_name)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Resolve the authenticated user from the session cookie.

    Raises ``UnauthorizedError`` (401) when there is no valid session or the
    user is missing/inactive.
    """

    session_id = get_session_id(request)
    if not session_id:
        raise UnauthorizedError()

    record = await read_session(session_id)
    if record is None:
        raise UnauthorizedError("Session expired or invalid.")

    try:
        user_id = uuid.UUID(str(record["user_id"]))
    except (KeyError, ValueError):
        raise UnauthorizedError("Session is malformed.") from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is unavailable.")

    # Expose the session id for downstream handlers (e.g. logout, CSRF issue).
    request.state.session_id = session_id
    return user


async def require_csrf(request: Request) -> None:
    """Enforce double-submit CSRF on mutating requests."""

    if request.method in _SAFE_METHODS:
        return

    settings = get_settings()
    header_token = request.headers.get(settings.csrf_header_name)
    session_id = get_session_id(request)
    if not validate_csrf_token(header_token, session_id):
        raise CSRFError()


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
