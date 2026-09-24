"""
Punto de entrada del backend (fábrica de la aplicación FastAPI).

    uvicorn backend.main:app --reload --port 8000

- API REST:   http://localhost:8000/api/...   (capa Controlador, backend/controllers)
- Swagger:    http://localhost:8000/docs
- Frontend:   http://localhost:8000/          (capa Vista, SPA de frontend/)

Arquitectura MVC:
    Vista (frontend/)  --HTTP/JSON-->  Controladores  -->  Modelos  -->  SQLite
                                              |
                                              +-->  Servicios (agente IA, Whisper, ETL, auth)
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.controllers.router import api_router
from backend.core.config import get_settings
from backend.core.errors import register_exception_handlers
from backend.models.db_connection import closing_connection, enable_wal
from backend.models.semantic_layer import ensure_semantic_layer
from backend.models.user_model import ensure_users
from backend.services.speech.speech_provider import get_speech_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("medipulse")


def _prepare_database() -> None:
    """Deja la BD lista antes de aceptar peticiones: WAL, capa semántica y usuarios iniciales."""
    settings = get_settings()
    if not settings.database_path.exists():
        logger.warning("No existe %s: se creará vacía. Ejecute `python setup_db.py`.", settings.database_path)
    enable_wal()
    with closing_connection() as conn:
        refresh_info = ensure_semantic_layer(conn)
        ensure_users(conn)
    logger.info("Capa semántica lista: %s", refresh_info)


def _log_runtime_configuration() -> None:
    settings = get_settings()
    if settings.auth.enabled and settings.auth.secret_is_ephemeral:
        logger.warning("JWT_SECRET no está definido en .env: se usa uno temporal "
                       "(las sesiones se cierran al reiniciar el servidor).")
    logger.info("Autenticación JWT: %s", "activa" if settings.auth.enabled else "DESACTIVADA (AUTH_ENABLED=false)")
    logger.info("IA: modo por defecto=%s, local=%s, nube=%s", settings.ai.default_mode,
                settings.ai.local.model, settings.ai.cloud.provider)


def _preload_speech_model() -> None:
    """Carga Whisper en un hilo aparte: el servidor queda disponible mientras el modelo se carga."""
    settings = get_settings()
    speech = get_speech_provider()
    if speech is not None and settings.voice.preload:
        threading.Thread(target=speech.preload, name="whisper-preload", daemon=True).start()
        logger.info("Voz: precargando Whisper '%s' en segundo plano", settings.voice.model_size)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Tareas de arranque de la aplicación (se ejecutan una vez por proceso)."""
    _prepare_database()
    _log_runtime_configuration()
    _preload_speech_model()
    yield


def create_app() -> FastAPI:
    """Construye la aplicación: middlewares, manejadores de errores, controladores y la Vista estática."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.1.0",
        description=(
            "Backend del Hospital Susana López de Valencia: API REST alineada con la SPA "
            "MediPulse, carga de archivos del HIS y asistente IA NL2SQL con switch Local/Nube."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    # La Vista se monta al final para que las rutas de la API tengan prioridad sobre "/".
    if settings.serve_frontend and settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    elif settings.serve_frontend:
        logger.warning("SERVE_FRONTEND=true pero no existe %s: solo se sirve la API.", settings.frontend_dir)
    return app


app = create_app()
