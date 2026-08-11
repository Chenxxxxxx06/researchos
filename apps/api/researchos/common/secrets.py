"""Small application-level envelope for credentials stored in the database.

The database column remains a string so existing installations do not need a
destructive migration. Legacy plaintext values are readable and are upgraded
the next time the owning integration is saved.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

_PREFIX = "enc:v1:"
_AAD = b"researchos:credential:v1"


class SecretDecryptionError(ValueError):
    """Raised when a stored encrypted value cannot be opened."""


def _key() -> bytes:
    material = f"researchos:v1:{get_settings().secret_key}".encode()
    return hashlib.sha256(material).digest()


def is_encrypted_secret(value: str) -> bool:
    return value.startswith(_PREFIX)


def encrypt_secret(value: str) -> str:
    value = value.strip()
    if not value or is_encrypted_secret(value):
        return value
    nonce = os.urandom(12)
    encrypted = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), _AAD)
    payload = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
    return f"{_PREFIX}{payload}"


def decrypt_secret(value: str) -> str:
    if not value or not is_encrypted_secret(value):
        return value
    try:
        payload = base64.urlsafe_b64decode(value[len(_PREFIX) :].encode("ascii"))
        nonce, encrypted = payload[:12], payload[12:]
        if len(nonce) != 12 or not encrypted:
            raise ValueError("invalid encrypted payload")
        return AESGCM(_key()).decrypt(nonce, encrypted, _AAD).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - normalize crypto/backend errors
        raise SecretDecryptionError(
            "The stored credential cannot be decrypted with the current server key."
        ) from exc


def mask_secret(value: str) -> str:
    try:
        plain = decrypt_secret(value)
    except SecretDecryptionError:
        return "****"
    return f"****{plain[-4:]}" if len(plain) > 4 else "****"
