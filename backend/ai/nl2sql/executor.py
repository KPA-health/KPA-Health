"""
Segunda barrera de seguridad: ejecución en SQLite de solo lectura con authorizer.

Aunque el validador estático fallara, el motor de SQLite rechaza en tiempo de
compilación cualquier escritura, PRAGMA, lectura de tablas internas o lectura
directa de columnas con datos personales. Las vistas de confianza sí pueden
leer esas columnas internamente (p. ej. VistaIngresos calcula la edad a partir
de la fecha de nacimiento), pero nunca las exponen.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from backend.ai.nl2sql.catalog import ALLOWED_TABLES, FORBIDDEN_COLUMNS
from backend.core.database import connect_readonly


class SQLExecutionError(Exception):
    """Error de SQLite al ejecutar la consulta (se devuelve al LLM para autocorrección)."""


class SQLPolicyError(SQLExecutionError):
    """El authorizer de SQLite bloqueó la consulta."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int


_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}

# Tablas internas de las que dependen las vistas. Cuando SQLite "aplana" una
# vista, verifica sus LEFT JOIN con una lectura SIN columna (column = '')
# atribuida al nivel superior; esa verificación no expone datos y se permite.
_VIEW_DEPENDENCIES = frozenset({
    "actividadingreso", "ingresogestion", "mapaservicio", "parametrossistema", "camaestadomanual",
})


def agent_authorizer(action: int, arg1: str | None, arg2: str | None,
                     _db_name: str | None, source: str | None) -> int:
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        if source is not None:
            # Lectura hecha por una vista del catálogo: la vista decide qué expone
            return sqlite3.SQLITE_OK
        table = (arg1 or "").lower()
        column = (arg2 or "").lower()
        if column == "" and table in _VIEW_DEPENDENCIES:
            return sqlite3.SQLITE_OK
        if table not in ALLOWED_TABLES or (table, column) in FORBIDDEN_COLUMNS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, float):
        return round(value, 4)
    return value


def execute_readonly(sql: str, timeout_seconds: float) -> QueryResult:
    started = time.perf_counter()
    conn = connect_readonly(authorizer=agent_authorizer, timeout_seconds=timeout_seconds)
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        rows = [[_json_safe(v) for v in row] for row in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        message = str(exc)
        if "not authorized" in message or "prohibited" in message:
            raise SQLPolicyError(
                "SQLite bloqueó la consulta: intenta leer tablas internas o columnas con datos "
                "personales (nombres, documentos, fechas de nacimiento, texto clínico libre)"
            ) from exc
        if "interrupted" in message:
            raise SQLExecutionError(
                f"La consulta superó el tiempo máximo de {timeout_seconds:.0f} s; simplifíquela"
            ) from exc
        raise SQLExecutionError(f"Error de SQLite: {message}") from exc
    finally:
        conn.close()
    return QueryResult(
        columns=columns, rows=rows, row_count=len(rows),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
