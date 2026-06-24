"""Password hashing (argon2id via pwdlib)."""

from __future__ import annotations

from pwdlib import PasswordHash

# Recommended configuration uses Argon2id.
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash. Never raises on mismatch."""

    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        return False
