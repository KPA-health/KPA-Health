"""
Punto de entrada del backend.

    uvicorn backend.main:app --reload --port 8000

- API REST:   http://localhost:8000/api/...
- Swagger:    http://localhost:8000/docs
- Frontend:   http://localhost:8000/   (sirve la SPA hospital-spa/)
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.ai.speech.base import get_speech_provider
from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.database import closing_connection, enable_wal
from backend.core.errors import register_exception_handlers
from backend.auth.repository import ensure_users
from backend.db.semantic_layer import ensure_semantic_layer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("medipulse")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if not settings.database_path.exists():
        logger.warning("No existe %s: se creará vacía. Ejecute `python setup_db.py`.",
                       settings.database_path)
    enable_wal()
    with closing_connection() as conn:
        info = ensure_semantic_layer(conn)
        ensure_users(conn)
    logger.info("Capa semántica lista: %s", info)
    if settings.auth.enabled and settings.auth.secret_is_ephemeral:
        logger.warning("JWT_SECRET no está definido en .env: se usa uno temporal "
                       "(las sesiones se cierran al reiniciar el servidor).")
    logger.info("Autenticación JWT: %s", "activa" if settings.auth.enabled else "DESACTIVADA (AUTH_ENABLED=false)")
    logger.info("IA: modo por defecto=%s, local=%s, nube=%s", settings.ai.default_mode,
                settings.ai.local.model, settings.ai.cloud.provider)
    speech = get_speech_provider()
    if speech is not None and settings.voice.preload:
        # En segundo plano: el servidor queda disponible mientras Whisper se carga
        threading.Thread(target=speech.preload, name="whisper-preload", daemon=True).start()
        logger.info("Voz: precargando Whisper '%s' en segundo plano", settings.voice.model_size)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
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

    # Se monta al final para que las rutas de la API tengan prioridad.
    if settings.serve_frontend and settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
