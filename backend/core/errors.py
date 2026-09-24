"""
Errores de dominio y manejadores HTTP.

El frontend (apiClient.js) lee `errorData.message` de las respuestas con error,
por eso todos los errores se serializan como {"message": ..., "detail": ...}.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("medipulse")


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ValidationError(AppError):
    status_code = 422


class ServiceUnavailableError(AppError):
    status_code = 503


class NotImplementedFeatureError(AppError):
    status_code = 501


def _payload(message: str, detail: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"success": False, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(exc.message, exc.detail))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Error HTTP"
        return JSONResponse(status_code=exc.status_code, content=_payload(message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in err.get("loc", [])[1:]), "error": err.get("msg")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content=_payload("Datos de entrada inválidos", errors)
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado: %s", exc)
        return JSONResponse(status_code=500, content=_payload("Error interno del servidor"))
