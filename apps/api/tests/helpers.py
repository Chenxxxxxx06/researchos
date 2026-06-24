"""Shared test helpers."""

from __future__ import annotations

from httpx import AsyncClient


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Build the X-CSRF-Token header from the client's csrf cookie."""

    token = client.cookies.get("ros_csrf")
    return {"X-CSRF-Token": token} if token else {}


async def register(
    client: AsyncClient,
    *,
    email: str,
    password: str = "password123",
    display_name: str = "Test User",
) -> dict:
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    resp.raise_for_status()
    return resp.json()


async def login(client: AsyncClient, *, email: str, password: str = "password123"):
    return await client.post("/auth/login", json={"email": email, "password": password})
