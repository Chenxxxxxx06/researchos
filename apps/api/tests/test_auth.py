"""Authentication, session, and CSRF tests."""

from __future__ import annotations

from httpx import AsyncClient

from .helpers import csrf_headers, login, register


async def test_register_creates_user_and_owner_org(client: AsyncClient) -> None:
    body = await register(client, email="alice@example.com", display_name="Alice")
    assert body["user"]["email"] == "alice@example.com"
    assert body["organization"]["role"] == "owner"
    # Session + CSRF cookies are set.
    assert client.cookies.get("ros_session")
    assert client.cookies.get("ros_csrf")


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await register(client, email="dup@example.com")
    resp = await client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "password123", "display_name": "X"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_email_normalized_case_insensitive(client: AsyncClient) -> None:
    await register(client, email="Mixed@Example.com")
    resp = await client.post(
        "/auth/register",
        json={"email": "mixed@example.com", "password": "password123", "display_name": "X"},
    )
    assert resp.status_code == 409


async def test_me_requires_session(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_me_returns_user_and_orgs(client: AsyncClient) -> None:
    await register(client, email="bob@example.com", display_name="Bob")
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "bob@example.com"
    assert len(body["organizations"]) == 1
    assert body["organizations"][0]["role"] == "owner"


async def test_login_wrong_password_is_generic_401(client: AsyncClient) -> None:
    await register(client, email="carol@example.com")
    resp = await login(client, email="carol@example.com", password="wrong-password")
    assert resp.status_code == 401
    # Message must not reveal whether the account exists.
    assert resp.json()["error"]["message"] == "Invalid credentials."


async def test_login_unknown_user_is_generic_401(client: AsyncClient) -> None:
    resp = await login(client, email="nobody@example.com", password="whatever12")
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid credentials."


async def test_logout_invalidates_session(client: AsyncClient) -> None:
    await register(client, email="dave@example.com")
    resp = await client.post("/auth/logout", headers=csrf_headers(client))
    assert resp.status_code == 204
    # After logout the session is gone.
    me = await client.get("/auth/me")
    assert me.status_code == 401


async def test_logout_requires_csrf(client: AsyncClient) -> None:
    await register(client, email="erin@example.com")
    resp = await client.post("/auth/logout")  # no X-CSRF-Token header
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"


async def test_mutation_with_bad_csrf_rejected(client: AsyncClient) -> None:
    await register(client, email="frank@example.com")
    resp = await client.post(
        "/organizations",
        json={"name": "Frank Lab"},
        headers={"X-CSRF-Token": "tampered-token"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"
