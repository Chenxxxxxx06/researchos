"""Paper search provider abstraction."""

from .base import PaperResult, PaperSearchFilters, PaperSearchProvider
from .registry import get_paper_provider

__all__ = [
    "PaperResult",
    "PaperSearchFilters",
    "PaperSearchProvider",
    "get_paper_provider",
]
