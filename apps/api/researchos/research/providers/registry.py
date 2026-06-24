"""Paper provider selection by configuration."""

from __future__ import annotations

import httpx

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .arxiv import ArxivProvider
from .base import PaperSearchProvider


def get_paper_provider(client: httpx.AsyncClient | None = None) -> PaperSearchProvider:
    """Return the configured paper search provider.

    Phase 2 supports arXiv only. The ``client`` argument lets callers (and
    tests) inject an HTTP client.
    """

    name = get_settings().paper_provider
    if name == "arxiv":
        return ArxivProvider(client=client)
    raise AppError(f"Unknown paper provider: {name}", code="config_error", http_status=500)
