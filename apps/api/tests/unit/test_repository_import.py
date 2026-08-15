"""Pure repository-import boundary checks."""

import pytest

from researchos.common.errors import ValidationError
from researchos.git.repository_import import _license_identifier, validate_github_url


@pytest.mark.parametrize(
    ("value", "owner", "repo"),
    [
        ("https://github.com/openai/codex", "openai", "codex"),
        ("https://github.com/OpenAI/codex.git", "OpenAI", "codex"),
    ],
)
def test_validate_github_url_accepts_exact_public_repository(
    value: str, owner: str, repo: str
) -> None:
    parsed = validate_github_url(value)
    assert (parsed.owner, parsed.repo) == (owner, repo)
    assert parsed.canonical_url == f"https://github.com/{owner}/{repo}"


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/openai/codex",
        "https://github.example/openai/codex",
        "https://github.com/openai/codex/tree/main",
        "https://user@github.com/openai/codex",
        "https://github.com/openai/codex?token=secret",
        "https://github.com/openai/codex#readme",
        "https://github.com/openai%2Fcodex",
    ],
)
def test_validate_github_url_rejects_noncanonical_or_unsafe_urls(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_github_url(value)


def test_license_detection_records_known_license_without_claiming_unknown() -> None:
    assert _license_identifier("Permission is hereby granted, free of charge") == "MIT"
    assert _license_identifier("custom research terms") is None
