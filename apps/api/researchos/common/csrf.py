"""CSRF protection (see PHASE1_DECISIONS P1-D3).

The CSRF token is not a bare random value: it is the session id signed with
itsdangerous (timestamped). The signed token is delivered in a JS-readable
cookie and must be echoed in the ``X-CSRF-Token`` header on every mutating
request. Validation checks the signature, the age, and that the embedded value
matches the caller's current session id.
"""

from __future__ import annotations

import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from researchos.common.config import get_settings

_SALT = "researchos-csrf"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=_SALT)


def issue_csrf_token(session_id: str) -> str:
    """Issue a signed CSRF token bound to the given session id."""

    return _serializer().dumps(session_id)


def validate_csrf_token(token: str | None, session_id: str | None) -> bool:
    """Validate a CSRF token against the caller's session id."""

    if not token or not session_id:
        return False
    settings = get_settings()
    try:
        bound = _serializer().loads(token, max_age=settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return False
    # Constant-time comparison of the bound session id.
    return hmac.compare_digest(str(bound), str(session_id))
