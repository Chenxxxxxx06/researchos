"""Paper provider selection by configuration.

``PAPER_PROVIDER`` is a comma-separated list (e.g. ``arxiv,s2,openalex``).
A single name yields that provider directly; several yield a federated
provider. The default ``arxiv`` keeps prior behavior byte-compatible.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .arxiv import ArxivProvider
from .base import PaperSearchProvider
from .federated import FederatedProvider
from .openalex import OpenAlexProvider
from .semantic_scholar import SemanticScholarProvider

_PROVIDER_FACTORIES: dict[str, Callable[..., PaperSearchProvider]] = {
    "arxiv": ArxivProvider,
    "s2": SemanticScholarProvider,
    "openalex": OpenAlexProvider,
}

PROVIDER_NAMES: frozenset[str] = frozenset(_PROVIDER_FACTORIES)


def get_provider_by_name(
    name: str, client: httpx.AsyncClient | None = None
) -> PaperSearchProvider:
    """Return a concrete provider by name (used by import verification)."""

    factory = _PROVIDER_FACTORIES.get(name)
    if factory is None:
        known = ", ".join(sorted(PROVIDER_NAMES))
        raise AppError(
            f"Unknown paper provider: {name}. Known providers: {known}.",
            code="config_error",
            http_status=500,
        )
    return factory(client=client)


def get_paper_provider(client: httpx.AsyncClient | None = None) -> PaperSearchProvider:
    """Return the configured provider (or a federated one for a list)."""

    names = [n.strip() for n in get_settings().paper_provider.split(",") if n.strip()]
    if not names:
        raise AppError(
            "PAPER_PROVIDER must name at least one provider.",
            code="config_error",
            http_status=500,
        )
    providers = [get_provider_by_name(name, client) for name in names]
    if len(providers) == 1:
        return providers[0]
    return FederatedProvider(providers)
