"""Slug generation utilities."""

from __future__ import annotations

import re
import secrets

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Produce a URL-safe slug fragment from arbitrary text."""

    slug = _slug_re.sub("-", value.strip().lower()).strip("-")
    return slug or "org"


def random_suffix(length: int = 6) -> str:
    """A short random suffix used to de-duplicate slugs."""

    return secrets.token_hex(length // 2 + 1)[:length]
