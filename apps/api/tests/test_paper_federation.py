"""Semantic Scholar / OpenAlex parsing, merge/dedup, and federated fan-out.

Provider-pure tests: recorded fixtures via httpx.MockTransport, no DB, no
network.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from researchos.research.providers.base import PaperResult, PaperSearchFilters, ProviderError
from researchos.research.providers.federated import (
    FederatedProvider,
    merge_results,
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
)
from researchos.research.providers.openalex import (
    OpenAlexProvider,
    _abstract_from_inverted_index,
)
from researchos.research.providers.semantic_scholar import SemanticScholarProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _client(payload: str, captured: list[httpx.Request] | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, text=payload, headers={"Content-Type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- Semantic Scholar --------------------------------------------------------
async def test_s2_search_parses_and_sends_expected_params() -> None:
    payload = (FIXTURES / "s2_search.json").read_text(encoding="utf-8")
    captured: list[httpx.Request] = []
    from datetime import date

    async with _client(payload, captured) as client:
        provider = SemanticScholarProvider(client=client)
        results = await provider.search(
            "vision",
            limit=20,
            filters=PaperSearchFilters(date_from=date(2024, 1, 1), offset=10),
        )

    params = dict(captured[0].url.params)
    assert captured[0].url.path.endswith("/paper/search")
    assert params["query"] == "vision"
    assert params["offset"] == "10"
    assert params["limit"] == "20"
    assert "title" in params["fields"] and "citationCount" in params["fields"]
    assert params["publicationDateOrYear"] == "2024-01-01:"

    first = results[0]
    assert first.source == "s2"
    assert first.external_id == "649def34f8be52c8b66281af98ae884c09aef38b"
    assert first.doi == "10.1234/abc"  # lowercased
    assert first.extra["arxiv_id"] == "2401.01234"
    assert first.citation_count == 87
    assert first.venue == "NeurIPS"
    assert first.pdf_url == "https://example.org/oa/2401.01234.pdf"
    assert first.published_at == datetime(2024, 1, 3, tzinfo=UTC)
    # publicationDate null -> year fallback (Jan 1).
    assert results[1].published_at == datetime(2023, 1, 1, tzinfo=UTC)


async def test_s2_fetch_by_ids_skips_404() -> None:
    payload = (FIXTURES / "s2_paper.json").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if "missing" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, text=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SemanticScholarProvider(client=client)
        results = await provider.fetch_by_ids(
            ["649def34f8be52c8b66281af98ae884c09aef38b", "missing"]
        )
    assert len(results) == 1
    assert results[0].title.startswith("Efficient Vision-Language")


# --- OpenAlex ----------------------------------------------------------------
def test_abstract_inverted_index_reconstruction() -> None:
    index = {"Graph": [0], "signal": [1, 4], "processing": [2], "handles": [3], "data.": [5]}
    assert (
        _abstract_from_inverted_index(index)
        == "Graph signal processing handles signal data."
    )
    assert _abstract_from_inverted_index(None) is None
    assert _abstract_from_inverted_index({}) is None


async def test_openalex_search_parses_and_sends_mailto() -> None:
    payload = (FIXTURES / "openalex_search.json").read_text(encoding="utf-8")
    captured: list[httpx.Request] = []
    async with _client(payload, captured) as client:
        provider = OpenAlexProvider(client=client, mailto="team@example.com")
        results = await provider.search(
            "vision", limit=25, filters=PaperSearchFilters(sort="latest", offset=25)
        )

    params = dict(captured[0].url.params)
    assert captured[0].url.path.endswith("/works")
    assert params["search"] == "vision"
    assert params["per-page"] == "25"
    assert params["page"] == "2"
    assert params["mailto"] == "team@example.com"
    assert params["sort"] == "publication_date:desc"

    first = results[0]
    assert first.source == "openalex"
    assert first.external_id == "W2741809807"  # short id
    assert first.doi == "10.1234/abc"  # prefix stripped + lowercased
    assert first.extra["arxiv_id"] == "2401.01234"  # regex over landing page
    expected_abstract = "We present an efficient pretraining method for vision-language models."
    assert first.abstract == expected_abstract
    assert first.venue == "Advances in Neural Information Processing Systems"
    assert first.citation_count == 91
    assert results[1].pdf_url is None


async def test_openalex_omits_mailto_when_empty() -> None:
    payload = (FIXTURES / "openalex_search.json").read_text(encoding="utf-8")
    captured: list[httpx.Request] = []
    async with _client(payload, captured) as client:
        provider = OpenAlexProvider(client=client, mailto="")
        await provider.search("vision", limit=10)
    assert "mailto" not in dict(captured[0].url.params)


async def test_openalex_fetch_by_ids() -> None:
    payload = (FIXTURES / "openalex_work.json").read_text(encoding="utf-8")
    async with _client(payload) as client:
        provider = OpenAlexProvider(client=client, mailto="")
        results = await provider.fetch_by_ids(["W2741809807"])
    assert len(results) == 1
    assert results[0].external_id == "W2741809807"
    assert results[0].doi == "10.1234/abc"


# --- normalizers / merge -----------------------------------------------------
def test_normalizers() -> None:
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("doi:10.1234/abc") == "10.1234/abc"
    assert normalize_arxiv_id("2401.01234v3") == "2401.01234"
    assert normalize_arxiv_id("solv-int/9701001") == "solv-int/9701001"
    assert normalize_title("  The  Éntropy—Formula! ") == "the entropy formula"


def _pr(**kwargs) -> PaperResult:
    defaults = {
        "source": "arxiv",
        "external_id": "x",
        "title": "T",
        "url": "http://example.org",
    }
    defaults.update(kwargs)
    return PaperResult(**defaults)


def test_merge_collapses_same_paper_from_three_providers() -> None:
    published = datetime(2024, 1, 3, tzinfo=UTC)
    arxiv = _pr(
        source="arxiv",
        external_id="2401.01234",
        title="Efficient Vision-Language Pretraining for Document Understanding",
        abstract="Short abstract.",
        venue="arXiv",
        published_at=published,
        url="http://arxiv.org/abs/2401.01234v2",
        pdf_url="http://arxiv.org/pdf/2401.01234v2",
        extra={"arxiv_id": "2401.01234"},
    )
    s2 = _pr(
        source="s2",
        external_id="649def34",
        title="Efficient Vision-Language Pretraining for Document Understanding",
        abstract="A much longer abstract with additional details about the corpus.",
        venue="NeurIPS",
        doi="10.1234/abc",
        citation_count=87,
        published_at=published,
        extra={"arxiv_id": "2401.01234"},
    )
    openalex = _pr(
        source="openalex",
        external_id="W2741809807",
        title="Efficient vision language pretraining for document understanding",
        venue="Advances in Neural Information Processing Systems",
        doi="10.1234/abc",
        citation_count=91,
        published_at=published,
        extra={"arxiv_id": "2401.01234"},
    )
    merged = merge_results({"arxiv": [arxiv], "s2": [s2], "openalex": [openalex]})

    assert len(merged) == 1
    result = merged[0]
    assert result.source == "arxiv" and result.external_id == "2401.01234"
    assert len(result.extra["sources"]) == 3
    assert result.citation_count == 91  # max
    assert result.venue == "NeurIPS"  # first non-arXiv venue in priority order
    assert result.doi == "10.1234/abc"
    assert result.abstract.startswith("A much longer")  # longest abstract wins


def test_merge_dedup_by_doi_only() -> None:
    a = _pr(source="s2", external_id="a", title="Completely Different Title One", doi="10.1/x")
    b = _pr(
        source="openalex", external_id="b", title="Another Unrelated Name Two", doi="10.1/X"
    )
    merged = merge_results({"s2": [a], "openalex": [b]})
    assert len(merged) == 1
    assert merged[0].source == "s2"  # s2 outranks openalex


def test_merge_dedup_by_arxiv_id_across_fields() -> None:
    a = _pr(source="arxiv", external_id="2401.01234", title="Title Alpha")
    b = _pr(
        source="openalex",
        external_id="W1",
        title="Totally Different Beta",
        extra={"arxiv_id": "2401.01234v2"},
    )
    merged = merge_results({"arxiv": [a], "openalex": [b]})
    assert len(merged) == 1
    assert merged[0].external_id == "2401.01234"


def test_merge_fuzzy_title_requires_author_or_year() -> None:
    a = _pr(
        source="s2",
        external_id="a",
        title="Robust Speech Recognition via Large-Scale Weak Supervision",
        authors=["Alec Radford"],
    )
    b = _pr(
        source="openalex",
        external_id="b",
        title="Robust Speech Recognition via Large Scale Weak Supervision Methods",
        authors=["A. Radford"],
    )
    merged = merge_results({"s2": [a], "openalex": [b]})
    assert len(merged) == 1  # fuzzy title + same first-author last name

    c = _pr(
        source="openalex",
        external_id="c",
        title="Robust Speech Recognition via Large Scale Weak Supervisions",
        authors=["Someone Else"],
    )
    merged2 = merge_results({"s2": [a], "openalex": [c]})
    assert len(merged2) == 2  # no author/year corroboration -> kept separate


def test_merge_keeps_distinct_papers_separate() -> None:
    a = _pr(source="arxiv", external_id="1", title="Graph Neural Networks for Chemistry")
    b = _pr(source="s2", external_id="2", title="Reinforcement Learning from Human Feedback")
    merged = merge_results({"arxiv": [a], "s2": [b]})
    assert len(merged) == 2


# --- federated fan-out -------------------------------------------------------
class _StubProvider:
    def __init__(self, name: str, results=None, *, error=None, hang=False):
        self.name = name
        self._results = results or []
        self._error = error
        self._hang = hang

    async def search(self, query, *, limit, filters=None):
        if self._hang:
            await asyncio.sleep(30)
        if self._error is not None:
            raise self._error
        return self._results

    async def fetch_by_ids(self, ids):
        return []


async def test_federated_partial_failure_yields_results_and_status() -> None:
    ok = _StubProvider("arxiv", [_pr(source="arxiv", external_id="1", title="Alpha Paper")])
    slow = _StubProvider("s2", hang=True)
    broken = _StubProvider("openalex", error=ProviderError("down"))

    federated = FederatedProvider([ok, slow, broken], timeout_seconds=0.05)
    results = await federated.search("q", limit=10)

    assert [r.external_id for r in results] == ["1"]
    assert federated.last_status == {
        "arxiv": "ok",
        "s2": "timeout",
        "openalex": "error:provider_error",
    }


async def test_federated_all_failed_raises() -> None:
    broken1 = _StubProvider("arxiv", error=ProviderError("down"))
    broken2 = _StubProvider("s2", error=ProviderError("down"))
    federated = FederatedProvider([broken1, broken2], timeout_seconds=0.05)
    with pytest.raises(ProviderError):
        await federated.search("q", limit=10)
    assert set(federated.last_status.values()) == {"error:provider_error"}


async def test_merge_provenance_ranks_survive_json() -> None:
    a = _pr(source="arxiv", external_id="1", title="Only Paper Here")
    merged = merge_results({"arxiv": [a]})
    sources = merged[0].extra["sources"]
    assert json.loads(json.dumps(sources)) == [
        {"provider": "arxiv", "external_id": "1", "url": "http://example.org", "rank": 0}
    ]
