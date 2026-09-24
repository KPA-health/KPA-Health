"""
Acceso a SQLite.

Dos tipos de conexión:
- `connect()`: lectura/escritura para la API REST y la carga de archivos.
- `connect_readonly()`: solo lectura, usada por el motor NL2SQL. Se abre con
  `mode=ro`, `PRAGMA query_only` y un *authorizer* de SQLite que bloquea
  escrituras, PRAGMAs, tablas internas y columnas con datos personales.
"""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from backend.core.config import get_settings


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = OFF")  # los extractos del HIS no son referencialmente íntegros
    return conn


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().database_path
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    return _configure(conn)


def enable_wal(db_path: Path | None = None) -> None:
    """WAL permite leer mientras una carga de archivo escribe."""
    with closing_connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")


def connect_readonly(
    db_path: Path | None = None,
    authorizer: Callable[..., int] | None = None,
    timeout_seconds: float | None = None,
) -> sqlite3.Connection:
    path = (db_path or get_settings().database_path).resolve()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    if timeout_seconds:
        deadline = time.monotonic() + timeout_seconds
        # Devolver un valor distinto de 0 interrumpe la consulta en curso
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    if authorizer is not None:
        conn.set_authorizer(authorizer)
    return conn


@contextmanager
def closing_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependencia de FastAPI: una conexión por petición."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (name,)
    ).fetchone()
    return row is not None
