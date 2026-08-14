"""DashScope (Aliyun Bailian) embedding adapter tests.

All HTTP traffic is intercepted by ``httpx.MockTransport`` — no real API
requests are ever made and no real key is used.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from researchos.knowledge import embeddings
from researchos.knowledge.embeddings import EmbeddingError, embed_texts
from researchos.knowledge.profiles import EmbeddingProfile

_QWEN_PROFILE = EmbeddingProfile(
    name="qwen-text-embedding-v4-1024",
    provider="dashscope",
    model="text-embedding-v4",
    dimensions=1024,
    normalize=True,
)


def _fake_settings(api_key: str) -> SimpleNamespace:
    return SimpleNamespace(
        dashscope_api_key=api_key,
        dashscope_base_url="https://dashscope.example.com/compatible-mode/v1",
    )


def _install(monkeypatch: pytest.MonkeyPatch, handler, *, api_key: str = "sk-test") -> None:
    monkeypatch.setattr(embeddings, "get_settings", lambda: _fake_settings(api_key))
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def _client(**kwargs) -> httpx.AsyncClient:  # noqa: ARG001 - timeout unused by mock
        return real_client(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", _client)


def _ok_response(
    batch: list[str], *, dimensions: int = 1024, shuffle: bool = False
) -> httpx.Response:
    items = [
        {"index": index, "embedding": [float(index)] * dimensions} for index in range(len(batch))
    ]
    if shuffle:
        items.reverse()
    return httpx.Response(200, json={"data": items})


async def test_dashscope_request_format_and_batching(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        batch = json.loads(request.content)["input"]
        # Return items out of order to prove index-based reordering.
        return _ok_response(batch, shuffle=True)

    _install(monkeypatch, handler)
    texts = [f"text-{index}" for index in range(23)]
    vectors = await embed_texts(texts, _QWEN_PROFILE)

    # Batch cap of 10 -> 10 + 10 + 3.
    assert len(requests) == 3
    batches = [json.loads(request.content) for request in requests]
    assert [len(batch["input"]) for batch in batches] == [10, 10, 3]
    for batch in batches:
        assert batch["model"] == "text-embedding-v4"
        assert batch["dimensions"] == 1024
    assert [request.headers["Authorization"] for request in requests] == ["Bearer sk-test"] * 3
    assert requests[0].url == "https://dashscope.example.com/compatible-mode/v1/embeddings"

    # Order is restored per batch: item i carries [float(i)] * 1024.
    assert len(vectors) == 23
    for offset, batch in enumerate(batches):
        for index, _ in enumerate(batch["input"]):
            assert vectors[offset * 10 + index] == [float(index)] * 1024


async def test_dashscope_retries_retryable_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, json={"error": "boom"})
        return _ok_response(json.loads(request.content)["input"])

    _install(monkeypatch, handler)
    vectors = await embed_texts(["hello"], _QWEN_PROFILE)
    assert calls == 2
    assert vectors == [[0.0] * 1024]


async def test_dashscope_rejects_wrong_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(json.loads(request.content)["input"], dimensions=512)

    _install(monkeypatch, handler)
    with pytest.raises(EmbeddingError, match="1024"):
        await embed_texts(["hello"], _QWEN_PROFILE)


async def test_dashscope_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP must not be attempted without an API key")

    _install(monkeypatch, handler, api_key="")
    with pytest.raises(EmbeddingError, match="DASHSCOPE_API_KEY"):
        await embed_texts(["hello"], _QWEN_PROFILE)
