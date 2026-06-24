"""Helpers for setting and clearing auth cookies with environment-aware flags.

See PHASE1_DECISIONS P1-D8: ``Secure`` is on only in production; the session
cookie is ``HttpOnly``; both default to ``SameSite=Lax``.
"""

from __future__ import annotations

from fastapi import Response

from researchos.common.config import get_settings


def set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    settings = get_settings()
    # Readable by JS so the SPA can echo it in the X-CSRF-Token header.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(key=name, domain=settings.cookie_domain, path="/")
