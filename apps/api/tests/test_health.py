"""Tests for health and readiness endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from researchos.health import router as health_router


async def test_healthz_ok(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "researchos-api"
    assert "version" in body


async def test_readyz_all_ok(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok() -> None:
        return None

    monkeypatch.setitem(health_router._PROBES, "postgres", _ok)
    monkeypatch.setitem(health_router._PROBES, "redis", _ok)
    monkeypatch.setitem(health_router._PROBES, "object_storage", _ok)

    resp = await client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert {c["name"] for c in body["checks"]} == {"postgres", "redis", "object_storage"}
    assert all(c["status"] == "ok" for c in body["checks"])


async def test_readyz_reports_dependency_failure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _ok() -> None:
        return None

    async def _fail() -> None:
        raise RuntimeError("redis down")

    monkeypatch.setitem(health_router._PROBES, "postgres", _ok)
    monkeypatch.setitem(health_router._PROBES, "redis", _fail)
    monkeypatch.setitem(health_router._PROBES, "object_storage", _ok)

    resp = await client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    redis_check = next(c for c in body["checks"] if c["name"] == "redis")
    assert redis_check["status"] == "error"
    assert "redis down" in redis_check["detail"]


async def test_request_id_header_present(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert "x-request-id" in {k.lower() for k in resp.headers}


async def test_request_validation_uses_error_envelope(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."
    assert "request_id" in body["error"]
