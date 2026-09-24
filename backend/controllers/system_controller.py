"""Controlador de sistema: salud del servicio y metadatos del dataset (/health, público)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.core.config import get_settings
from backend.models.db_connection import count_rows, get_db
from backend.models.his_schema import LOAD_ORDER
from backend.models.semantic_layer import REFERENCE_KEY, REFRESHED_AT_KEY, get_param

router = APIRouter(tags=["Sistema"])


@router.get("/health")
def get_health(conn: sqlite3.Connection = Depends(get_db)):
    """
    Estado del backend y conteo de registros por tabla del HIS.

    La pantalla "Gestión de datos" usa `rowCounts`; una tabla aún no creada se
    reporta como null en lugar de hacer fallar todo el chequeo.
    """
    settings = get_settings()
    ai = settings.ai
    cloud_model = ai.cloud.gemini_model if ai.cloud.provider == "gemini" else ai.cloud.openai_model
    return {
        "status": "ok",
        "database": settings.database_path.name,
        "referenceDatetime": get_param(conn, REFERENCE_KEY),
        "semanticLayerRefreshedAt": get_param(conn, REFRESHED_AT_KEY),
        "rowCounts": {table: count_rows(conn, table) for table in LOAD_ORDER},
        "ai": {"defaultMode": ai.default_mode, "localModel": ai.local.model, "cloudModel": cloud_model},
        "authEnabled": settings.auth.enabled,
    }
