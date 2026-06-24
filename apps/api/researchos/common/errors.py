"""Typed application errors and FastAPI exception handlers.

All deliberate, user-facing failures should raise an ``AppError`` subclass so
the API returns a consistent, machine-readable envelope:

    {"error": {"code": "...", "message": "...", "request_id": "..."}}
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Base class for expected, typed application errors."""

    code: str = "internal_error"
    http_status: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422
    message = "Request validation failed."


class UnauthorizedError(AppError):
    code = "unauthorized"
    http_status = 401
    message = "Authentication is required."


class PermissionError(AppError):
    code = "permission_denied"
    http_status = 403
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    code = "conflict"
    http_status = 409
    message = "The resource already exists."


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404
    message = "The requested resource was not found."


class DependencyError(AppError):
    code = "dependency_unavailable"
    http_status = 503
    message = "A required dependency is unavailable."


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(code: str, message: str, request_id: str | None, details: dict[str, Any]) -> dict:
    payload: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details:
        payload["details"] = details
    return {"error": payload}


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers that convert exceptions into the error envelope."""

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)
        errors = jsonable_encoder(exc.errors())
        logger.warning(
            "request_validation_error",
            request_id=request_id,
            errors=errors,
        )
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error",
                "Request validation failed.",
                request_id,
                {"errors": errors},
            ),
        )

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        logger.warning(
            "app_error",
            code=exc.code,
            message=exc.message,
            http_status=exc.http_status,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(exc.code, exc.message, request_id, exc.details),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.error("unhandled_exception", error=str(exc), request_id=request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An unexpected error occurred.", request_id, {}),
        )
