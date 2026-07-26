"""arXiv provider tests: parsing, query compiler, id normalization, retry,
bozo guard, fetch_by_ids. No network: recorded fixtures via mock transports."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from researchos.research.providers.arxiv import (
    ArxivProvider,
    ProviderError,
    _split_external_id,
    compile_arxiv_query,
)
from researchos.research.providers.base import PaperSearchFilters
from researchos.research.providers.retry import fetch_with_retry

FIXTURES = Path(__file__).parent / "fixtures"


def _client_serving(xml: str, captured: list[httpx.Request] | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, text=xml, headers={"Content-Type": "application/atom+xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- parsing -----------------------------------------------------------------
async def test_arxiv_parses_results() -> None:
    xml = (FIXTURES / "arxiv_sample.xml").read_text(encoding="utf-8")
    async with _client_serving(xml) as client:
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
    # extra stores the bare id (not the abs URL) plus the version.
    assert first.extra["arxiv_id"] == "2401.01234"
    assert first.extra["arxiv_version"] == "v2"
    # Abstract hard line-wraps are folded.
    assert "\n" not in (first.abstract or "")


async def test_arxiv_captures_categories_and_doi() -> None:
    xml = (FIXTURES / "arxiv_fielded.xml").read_text(encoding="utf-8")
    async with _client_serving(xml) as client:
        results = await ArxivProvider(client=client).search("x", limit=10)

    first = results[0]
    assert first.doi == "10.1234/abc"
    assert first.categories == ["cs.LG", "cs.CL"]
    assert first.extra["arxiv_primary_category"] == "cs.LG"


async def test_arxiv_old_style_ids_preserved() -> None:
    xml = (FIXTURES / "arxiv_oldstyle.xml").read_text(encoding="utf-8")
    async with _client_serving(xml) as client:
        results = await ArxivProvider(client=client).search("oldstyle", limit=10)

    by_id = {r.external_id: r for r in results}
    assert "solv-int/9701001" in by_id
    assert "math/0211159" in by_id
    assert "cond-mat/0703470" in by_id  # v2 stripped, prefix intact
    assert by_id["cond-mat/0703470"].extra["arxiv_version"] == "v2"


def test_split_external_id_table() -> None:
    cases = [
        ("http://arxiv.org/abs/solv-int/9701001", ("solv-int/9701001", None)),
        ("http://arxiv.org/abs/2401.01234v2", ("2401.01234", "v2")),
        ("http://arxiv.org/abs/math/0211159", ("math/0211159", None)),
        ("http://arxiv.org/abs/cond-mat/0703470v2", ("cond-mat/0703470", "v2")),
        ("2401.01234", ("2401.01234", None)),
    ]
    for raw, expected in cases:
        assert _split_external_id(raw) == expected


# --- query compiler ----------------------------------------------------------
def test_compiler_neutralizes_operator_injection() -> None:
    compiled = compile_arxiv_query('cats" OR all:dogs', PaperSearchFilters())
    assert '"' not in compiled
    assert "(" == compiled[0]  # our own grouping only
    # The user's OR operator token is dropped; terms are AND-joined.
    assert " OR " not in compiled
    assert "all:cats" in compiled
    # "all:dogs" had its colon stripped -> harmless content tokens.
    assert "all:all" in compiled and "all:dogs" in compiled


def test_compiler_fielded_terms_categories_dates() -> None:
    filters = PaperSearchFilters(
        categories=["cs.LG", "cs.RO"],
        author="Sergey Levine",
        title="diffusion",
        date_from=date(2025, 1, 1),
        date_to=date(2025, 6, 30),
    )
    compiled = compile_arxiv_query("planning", filters)
    assert "(all:planning)" in compiled
    assert 'au:"Sergey Levine"' in compiled
    assert "ti:diffusion" in compiled  # single word -> unquoted
    assert "(cat:cs.LG OR cat:cs.RO)" in compiled
    assert "submittedDate:[202501010000 TO 202506302359]" in compiled


def test_compiler_year_fallback_and_open_end() -> None:
    compiled = compile_arxiv_query("x", PaperSearchFilters(year_from=2020, year_to=2021))
    assert "submittedDate:[202001010000 TO 202112312359]" in compiled
    open_ended = compile_arxiv_query("x", PaperSearchFilters(year_to=2021))
    assert "submittedDate:[190001010000 TO 202112312359]" in open_ended


def test_compiler_empty_query_with_categories_ok_and_bare_empty_raises() -> None:
    compiled = compile_arxiv_query("", PaperSearchFilters(categories=["cs.LG"]))
    assert compiled == "(cat:cs.LG)"
    with pytest.raises(ProviderError):
        compile_arxiv_query("", PaperSearchFilters())
    with pytest.raises(ProviderError):
        compile_arxiv_query("AND OR", None)  # operator-only text is dropped


def test_filters_reject_bad_category() -> None:
    with pytest.raises(ValueError):
        PaperSearchFilters(categories=["cs.LG)", "cs.CL"])


async def test_search_request_params_sort_and_pagination() -> None:
    xml = (FIXTURES / "arxiv_fielded.xml").read_text(encoding="utf-8")
    captured: list[httpx.Request] = []
    async with _client_serving(xml, captured) as client:
        provider = ArxivProvider(client=client)
        await provider.search(
            "vision",
            limit=20,
            filters=PaperSearchFilters(categories=["cs.LG"], sort="latest", offset=20),
        )

    params = dict(captured[0].url.params)
    assert params["start"] == "20"
    assert params["max_results"] == "20"
    assert params["sortBy"] == "submittedDate"
    assert params["sortOrder"] == "descending"
    assert "cat:cs.LG" in params["search_query"]


# --- retry / bozo ------------------------------------------------------------
async def test_fetch_with_retry_retries_statuses_then_succeeds() -> None:
    calls = {"n": 0}
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def fn() -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, text="ok")

    resp = await fetch_with_retry(fn, attempts=3, base_delay=0.5, sleep=fake_sleep)
    assert resp.status_code == 200
    assert calls["n"] == 3
    assert len(delays) == 2
    assert delays[1] > delays[0] > 0  # exponential backoff


async def test_fetch_with_retry_transport_error_exhaustion_reraises() -> None:
    calls = {"n": 0}

    async def fake_sleep(_: float) -> None:
        return None

    async def fn() -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(httpx.ConnectError):
        await fetch_with_retry(fn, attempts=3, sleep=fake_sleep)
    assert calls["n"] == 3


async def test_fetch_with_retry_does_not_retry_non_listed_status() -> None:
    calls = {"n": 0}

    async def fn() -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    resp = await fetch_with_retry(fn, attempts=3, sleep=lambda _: _never())
    assert resp.status_code == 404
    assert calls["n"] == 1


async def _never() -> None:  # pragma: no cover - called only on regression
    raise AssertionError("sleep must not be called")


async def test_arxiv_provider_error_on_http_failure() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ArxivProvider(client=client, retry_base_delay=0.0)
        with pytest.raises(ProviderError):
            await provider.search("anything", limit=5)
    assert calls["n"] == 3  # retried before failing


async def test_arxiv_bozo_feed_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<<<not really xml>>>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ArxivProvider(client=client, retry_base_delay=0.0)
        with pytest.raises(ProviderError):
            await provider.search("anything", limit=5)


# --- fetch_by_ids ------------------------------------------------------------
async def test_fetch_by_ids_batches_one_request() -> None:
    xml = (FIXTURES / "arxiv_idlist.xml").read_text(encoding="utf-8")
    captured: list[httpx.Request] = []
    async with _client_serving(xml, captured) as client:
        provider = ArxivProvider(client=client)
        results = await provider.fetch_by_ids(["2401.01234", "2312.05678"])

    assert len(captured) == 1
    params = dict(captured[0].url.params)
    assert params["id_list"] == "2401.01234,2312.05678"
    assert {r.external_id for r in results} == {"2401.01234", "2312.05678"}
    assert results[0].title.startswith("Efficient Vision-Language")
