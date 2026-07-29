"""Small stdlib HTTP client for the ResearchOS API."""

from __future__ import annotations

import json
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .config import _private_file, cli_home


class APIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class ResearchOSClient:
    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.cookie_path = cli_home() / "cookies.txt"
        self.cookies = MozillaCookieJar(str(self.cookie_path))
        if self.cookie_path.exists():
            try:
                self.cookies.load(ignore_discard=True, ignore_expires=True)
            except (OSError, ValueError):
                pass
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_url}{path}"
        if query:
            values = {key: value for key, value in query.items() if value is not None}
            if values:
                url = f"{url}?{urlencode(values)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json", "User-Agent": "ResearchOS-CLI/0.1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            csrf = self._cookie_value("ros_csrf")
            if csrf:
                headers["X-CSRF-Token"] = csrf
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read()
                result = json.loads(raw) if raw else None
        except HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw) if raw else {}
                error = payload.get("error", {})
                message = error.get("message") or str(exc)
                code = error.get("code")
            except (json.JSONDecodeError, AttributeError):
                message, code = str(exc), None
            raise APIError(message, status=exc.code, code=code) from exc
        except URLError as exc:
            raise APIError(f"Cannot reach ResearchOS API at {self.api_url}: {exc.reason}") from exc
        self._save_cookies()
        return result

    def login(self, email: str, password: str) -> dict[str, Any]:
        result = self.request("POST", "/auth/login", body={"email": email, "password": password})
        return dict(result)

    def register(self, email: str, password: str, display_name: str) -> dict[str, Any]:
        result = self.request(
            "POST",
            "/auth/register",
            body={"email": email, "password": password, "display_name": display_name},
        )
        return dict(result)

    def _cookie_value(self, name: str) -> str | None:
        for cookie in self.cookies:
            if cookie.name == name:
                return cookie.value
        return None

    def _save_cookies(self) -> None:
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies.save(ignore_discard=True, ignore_expires=True)
        _private_file(Path(self.cookie_path))
