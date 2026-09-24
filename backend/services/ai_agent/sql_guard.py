"""
Primera barrera de seguridad: análisis estático del SQL generado por el LLM (sqlglot).

Reglas:
- exactamente una sentencia y debe ser de lectura (SELECT / WITH / UNION ...),
- ningún nodo de escritura, DDL, PRAGMA, ATTACH o comando,
- solo tablas/vistas del catálogo (más los CTE que la propia consulta define),
- ninguna columna con datos personales y nada de SELECT * sobre tablas con datos personales,
- LIMIT obligatorio (se inyecta si falta o se recorta si excede el máximo).

La segunda barrera es el authorizer de SQLite en sql_executor.py.
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from backend.services.ai_agent.catalog import (
    ALLOWED_TABLES, FORBIDDEN_COLUMN_NAMES, TABLES_WITH_PERSONAL_DATA,
)


class SQLGuardError(Exception):
    """La consulta viola la política de seguridad del agente."""


_READ_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_FORBIDDEN_NODE_NAMES = (
    "Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable", "Command", "Pragma",
    "Attach", "Detach", "Transaction", "Commit", "Rollback", "Merge", "Copy", "LoadData", "Set",
)
_FORBIDDEN_NODES = tuple(
    getattr(exp, name) for name in _FORBIDDEN_NODE_NAMES if hasattr(exp, name)
)
_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE)


def clean_sql_text(sql: str) -> str:
    """Quita cercas de markdown (```sql) y el punto y coma final que suelen añadir los LLM."""
    text = _FENCE.sub("", sql.strip()).strip()
    return text.rstrip(";").strip()


def validate_and_limit(sql: str, max_rows: int) -> str:
    """Valida el SQL y devuelve el texto final a ejecutar (con LIMIT garantizado)."""
    text = clean_sql_text(sql)
    if not text:
        raise SQLGuardError("La consulta SQL está vacía")

    try:
        statements = [s for s in sqlglot.parse(text, read="sqlite") if s is not None]
    except ParseError as exc:
        raise SQLGuardError(f"SQL inválido para SQLite: {exc}") from exc
    if len(statements) != 1:
        raise SQLGuardError("Solo se permite una sentencia SQL por consulta")

    root = statements[0]
    if not isinstance(root, _READ_ROOTS):
        raise SQLGuardError("Solo se permiten consultas de lectura (SELECT)")

    for node in root.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SQLGuardError(f"Operación no permitida en la consulta: {type(node).__name__}")

    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    tables = {t.name.lower() for t in root.find_all(exp.Table) if t.name}
    unknown = sorted(tables - ALLOWED_TABLES - cte_names)
    if unknown:
        raise SQLGuardError(f"Tablas no permitidas o inexistentes: {', '.join(unknown)}")

    for column in root.find_all(exp.Column):
        if column.name.lower() in FORBIDDEN_COLUMN_NAMES:
            raise SQLGuardError(
                f"La columna '{column.name}' contiene datos personales y no puede consultarse"
            )
    if tables & TABLES_WITH_PERSONAL_DATA and any(
        isinstance(star.parent, exp.Select) or isinstance(star.parent, exp.Column)
        for star in root.find_all(exp.Star)
    ):
        raise SQLGuardError(
            "SELECT * no está permitido sobre tablas con datos personales; liste las columnas"
        )

    return _enforce_limit(root, text, max_rows)


def _enforce_limit(root: exp.Expression, text: str, max_rows: int) -> str:
    """Añade LIMIT si falta o lo recorta si supera max_rows; si ya es válido, respeta el texto original."""
    limit = root.args.get("limit")
    if limit is None:
        return f"{text}\nLIMIT {max_rows}"
    try:
        current = int(limit.expression.this) if limit.expression is not None else None
    except (TypeError, ValueError):
        current = None
    if current is not None and current <= max_rows:
        return text
    root.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return root.sql(dialect="sqlite")
