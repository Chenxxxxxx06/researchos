"""Paper search provider abstraction."""

from .base import (
    PaperImportRef,
    PaperResult,
    PaperSearchFilters,
    PaperSearchProvider,
    ProviderError,
)
from .federated import FederatedProvider, merge_results
from .registry import PROVIDER_NAMES, get_paper_provider, get_provider_by_name

__all__ = [
    "FederatedProvider",
    "PROVIDER_NAMES",
    "PaperImportRef",
    "PaperResult",
    "PaperSearchFilters",
    "PaperSearchProvider",
    "ProviderError",
    "get_paper_provider",
    "get_provider_by_name",
    "merge_results",
]
