"""
Errores de dominio y su traducción a respuestas HTTP.

Por qué existe este módulo: los modelos y servicios NO conocen HTTP. Cuando una
regla de negocio falla lanzan una excepción de dominio (``NotFoundError``,
``ConflictError``...) y los manejadores registrados aquí la convierten en el
código de estado adecuado. Así ningún controlador repite bloques try/except
para traducir errores y todas las respuestas de error tienen la misma forma.

Contrato con el frontend (apiClient.js lee ``errorData.message``)::

    {"success": false, "message": "<texto para el usuario>", "detail": <opcional>}

Tabla de códigos:
    400 BadRequestError        regla de negocio o parámetro inválido
    401 UnauthorizedError      sin sesión o token inválido/vencido
    403 ForbiddenError         el rol no tiene el permiso del módulo
    404 NotFoundError          el recurso no existe
    409 ConflictError          estado incompatible (cama ocupada, usuario repetido)
    413 PayloadTooLargeError   archivo o audio por encima del límite
    422 (FastAPI)              el cuerpo/parámetros no cumplen el esquema Pydantic
    429 TooManyRequestsError   bloqueo temporal por intentos de login fallidos
    500                        error no controlado o fallo de SQLite (se registra en el log)
    501 NotImplementedFeatureError  funcionalidad deshabilitada por configuración
    503 ServiceUnavailableError     dependencia externa caída (LLM, Whisper, BD bloqueada)
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("medipulse")


class AppError(Exception):
    """Base de los errores de dominio: lleva un mensaje apto para mostrar al usuario."""

    status_code = 400

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class PayloadTooLargeError(AppError):
    status_code = 413


class TooManyRequestsError(AppError):
    status_code = 429


class NotImplementedFeatureError(AppError):
    status_code = 501


class ServiceUnavailableError(AppError):
    status_code = 503


def build_error_body(message: str, detail: Any = None) -> dict[str, Any]:
    """Cuerpo JSON uniforme de todas las respuestas de error."""
    body: dict[str, Any] = {"success": False, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Registra la traducción excepción -> respuesta HTTP en la aplicación."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=build_error_body(exc.message, exc.detail))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Error HTTP"
        return JSONResponse(status_code=exc.status_code, content=build_error_body(message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Se descarta el primer elemento de `loc` ("body", "query"...) para mostrar solo el campo
        errors = [
            {"field": ".".join(str(part) for part in err.get("loc", [])[1:]), "error": err.get("msg")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=build_error_body("Datos de entrada inválidos", errors))

    @app.exception_handler(sqlite3.DatabaseError)
    async def handle_database_error(_: Request, exc: sqlite3.DatabaseError) -> JSONResponse:
        # "database is locked": otra escritura larga (p. ej. una carga de archivo) tiene la BD;
        # es transitorio, por eso 503 y no 500.
        if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower():
            logger.warning("Base de datos ocupada: %s", exc)
            return JSONResponse(
                status_code=503,
                content=build_error_body("La base de datos está ocupada. Intente de nuevo en unos segundos."),
            )
        logger.exception("Error de base de datos: %s", exc)
        return JSONResponse(status_code=500, content=build_error_body("Error interno de la base de datos"))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Último recurso: nunca se filtra el detalle interno (traza, SQL) al cliente
        logger.exception("Error no controlado: %s", exc)
        return JSONResponse(status_code=500, content=build_error_body("Error interno del servidor"))
