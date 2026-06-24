"""arXiv provider parsing tests. No network: a recorded fixture is served via a
mock httpx transport."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from researchos.research.providers.arxiv import ArxivProvider

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_sample.xml"


def _mock_client() -> httpx.AsyncClient:
    xml = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml, headers={"Content-Type": "application/atom+xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_arxiv_parses_results() -> None:
    async with _mock_client() as client:
        provider = ArxivProvider(client=client)
        results = await provider.search("vision language", limit=10)

    assert len(results) == 2
    first = results[0]
    assert first.source == "arxiv"
    assert first.external_id == "2401.01234"  # version stripped
    assert "Document Understanding" in first.title
    assert first.authors == ["Alice Researcher", "Bob Scientist"]
    assert first.pdf_url == "http://arxiv.org/pdf/2401.01234v2"
    assert first.published_at is not None
    assert first.citation_key == "arxiv:2401.01234"


async def test_arxiv_provider_error_on_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    from researchos.research.providers.arxiv import ProviderError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ArxivProvider(client=client)
        with pytest.raises(ProviderError):
            await provider.search("anything", limit=5)
