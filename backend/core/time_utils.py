"""Utilidades de fecha/hora con el formato de texto que usa la base de datos."""
from __future__ import annotations

from datetime import datetime

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    """Fecha y hora local actual en el formato de texto de la base de datos."""
    return datetime.now().strftime(DB_DATETIME_FORMAT)


def to_minutes_precision(value: str | None) -> str | None:
    """'2026-09-21 14:33:44' -> '2026-09-21 14:33' (formato que muestra el frontend)."""
    return value[:16] if value else value
