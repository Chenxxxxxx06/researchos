from __future__ import annotations

import pytest

from researchos.common.secrets import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
    mask_secret,
)


def test_secret_round_trip_and_mask() -> None:
    stored = encrypt_secret("credential-1234")
    assert is_encrypted_secret(stored)
    assert stored != "credential-1234"
    assert decrypt_secret(stored) == "credential-1234"
    assert mask_secret(stored) == "****1234"


def test_plaintext_legacy_value_remains_readable() -> None:
    assert decrypt_secret("legacy-value") == "legacy-value"
    assert mask_secret("legacy-value") == "****alue"


def test_tampered_secret_fails_closed() -> None:
    stored = encrypt_secret("credential-1234")
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(stored[:-2] + "aa")
