"""Salud del sistema y metadatos del dataset."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

import setup_db

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.db.semantic_layer import REFERENCE_KEY, REFRESHED_AT_KEY, get_param

router = APIRouter(tags=["Sistema"])


@router.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    settings = get_settings()
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in setup_db.LOAD_ORDER
    }
    return {
        "status": "ok",
        "database": str(settings.database_path.name),
        "referenceDatetime": get_param(conn, REFERENCE_KEY),
        "semanticLayerRefreshedAt": get_param(conn, REFRESHED_AT_KEY),
        "rowCounts": counts,
        "ai": {
            "defaultMode": settings.ai.default_mode,
            "localModel": settings.ai.local.model,
            "cloudModel": settings.ai.cloud.gemini_model
            if settings.ai.cloud.provider == "gemini" else settings.ai.cloud.openai_model,
        },
        "authEnabled": settings.auth.enabled,
    }
