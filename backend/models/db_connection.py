"""
Conexión a SQLite (capa Modelo).

Es el ÚNICO módulo que abre conexiones a la base de datos. Ofrece dos tipos:

- ``connect()``: lectura/escritura, para la API REST y la carga de archivos.
- ``connect_readonly()``: solo lectura, para el agente NL2SQL. Se abre con
  ``mode=ro``, ``PRAGMA query_only`` y, opcionalmente, un *authorizer* de SQLite
  que bloquea escrituras, PRAGMAs, tablas internas y columnas con datos personales.
  Así, aunque un LLM generara SQL malicioso, el motor lo rechazaría.
"""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from backend.core.config import get_settings

# Milisegundos que SQLite espera a que se libere un bloqueo antes de fallar
BUSY_TIMEOUT_MS = 10_000
# Cada cuántas instrucciones de la VM de SQLite se revisa el tiempo límite de una consulta
PROGRESS_HANDLER_STEPS = 10_000


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    # Los extractos del HIS no son referencialmente íntegros (hay ingresos sin paciente)
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Conexión de lectura/escritura con filas accesibles por nombre de columna."""
    path = db_path or get_settings().database_path
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, check_same_thread=False)
    return _configure(conn)


def connect_readonly(
    db_path: Path | None = None,
    authorizer: Callable[..., int] | None = None,
    timeout_seconds: float | None = None,
) -> sqlite3.Connection:
    """
    Conexión de solo lectura, opcionalmente con authorizer y tiempo máximo por consulta.

    El tiempo máximo se implementa con un *progress handler*: SQLite lo invoca
    periódicamente y, si devuelve un valor distinto de 0, interrumpe la consulta.
    Protege al servidor de un SQL generado por IA que haga un producto cartesiano.
    """
    path = (db_path or get_settings().database_path).resolve()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_MS / 1000,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    if timeout_seconds:
        deadline = time.monotonic() + timeout_seconds
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), PROGRESS_HANDLER_STEPS)
    if authorizer is not None:
        conn.set_authorizer(authorizer)
    return conn


@contextmanager
def closing_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager que garantiza el cierre de la conexión (uso fuera de peticiones HTTP)."""
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def enable_wal(db_path: Path | None = None) -> None:
    """Activa el modo WAL: permite leer mientras una carga de archivo está escribiendo."""
    with closing_connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependencia de FastAPI: una conexión por petición, cerrada siempre al terminar."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convierte filas de SQLite en diccionarios serializables."""
    return [dict(row) for row in rows]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """True si existe una tabla o vista con ese nombre."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (name,)
    ).fetchone()
    return row is not None


def count_rows(conn: sqlite3.Connection, table: str) -> int | None:
    """Número de filas de una tabla; None si la tabla aún no existe (BD sin cargar)."""
    if not table_exists(conn, table):
        return None
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
