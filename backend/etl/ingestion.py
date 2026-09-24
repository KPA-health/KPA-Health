"""
Carga incremental de archivos del HIS (POST /api/upload/{type}).

Reutiliza literalmente la lectura y limpieza de setup_db.py
(`read_source_file` + `clean_dataframe`) y agrega lo que una carga repetible
necesita: validación de columnas, tabla de staging e inserción idempotente
(volver a subir el mismo archivo no duplica registros).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import IO

import pandas as pd

import setup_db
from backend.core.errors import ValidationError
from backend.db.semantic_layer import refresh_materialized

logger = logging.getLogger("medipulse.etl")


@dataclass(frozen=True)
class UploadTarget:
    table: str
    # Clave natural usada para no duplicar filas en tablas con id autoincremental
    natural_key: tuple[str, ...] | None = None


# Tipos que envía el frontend (MediPulse.DataSync.uploadFile) -> tabla del HIS
UPLOAD_TARGETS: dict[str, UploadTarget] = {
    "paciente": UploadTarget("Paciente"),
    "triage": UploadTarget("Triage"),
    "ingresos": UploadTarget("Ingresos"),
    "atencion": UploadTarget("Atencion", natural_key=("OidIngreso", "FechaAtencion")),
    "medicamento": UploadTarget("MedicamentoInsumo"),
    "servicios": UploadTarget("Servicios"),
    "cirugia": UploadTarget(
        "ProgramacionCirugia",
        natural_key=("ConsecutivoProgramacion", "IdPaciente", "OidIngreso", "CodigoServicio"),
    ),
}

# Alias tolerados (nombres de archivo / tabla)
_ALIASES = {
    "pacientes": "paciente", "ingreso": "ingresos", "atenciones": "atencion",
    "medicamentos": "medicamento", "medicamentoinsumo": "medicamento", "farmacia": "medicamento",
    "servicio": "servicios", "cirugias": "cirugia", "programacioncirugia": "cirugia",
}

_AUTOINCREMENT_COLUMNS = {"IdAtencion", "IdProgramacion"}


def resolve_target(upload_type: str) -> UploadTarget:
    key = upload_type.strip().lower()
    key = _ALIASES.get(key, key)
    if key not in UPLOAD_TARGETS:
        raise ValidationError(
            f"Tipo de carga no soportado: '{upload_type}'",
            {"supportedTypes": sorted(UPLOAD_TARGETS)},
        )
    return UPLOAD_TARGETS[key]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _align_columns(df: pd.DataFrame, table_columns: list[str]) -> tuple[pd.DataFrame, list[str]]:
    expected = [c for c in table_columns if c not in _AUTOINCREMENT_COLUMNS]
    received = [c.strip() for c in df.columns]
    missing = [c for c in expected if c not in received]
    if missing:
        raise ValidationError(
            "El archivo no tiene las columnas esperadas para esta tabla",
            {"missingColumns": missing, "expectedColumns": expected, "receivedColumns": received},
        )
    ignored = [c for c in received if c not in expected]
    return df[expected], ignored


def ingest_file(
    conn: sqlite3.Connection, upload_type: str, file_obj: IO[bytes], file_name: str
) -> dict:
    target = resolve_target(upload_type)
    started = time.perf_counter()

    try:
        raw = setup_db.read_source_file(file_obj)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise ValidationError(f"No se pudo leer el archivo '{file_name}': {exc}") from exc

    raw.columns = raw.columns.str.strip()
    columns = _table_columns(conn, target.table)
    raw, ignored_columns = _align_columns(raw, columns)
    clean = setup_db.clean_dataframe(raw, target.table)
    if clean.empty:
        raise ValidationError(f"El archivo '{file_name}' no contiene registros")

    staging = f"_staging_{target.table}"
    insert_cols = ", ".join(clean.columns)
    before = conn.execute(f"SELECT COUNT(*) FROM {target.table}").fetchone()[0]
    try:
        clean.to_sql(staging, conn, if_exists="replace", index=False)
        if target.natural_key:
            match = " AND ".join(f"t.{k} IS s.{k}" for k in target.natural_key)
            conn.execute(
                f"INSERT INTO {target.table} ({insert_cols}) "
                f"SELECT {insert_cols} FROM {staging} s "
                f"WHERE NOT EXISTS (SELECT 1 FROM {target.table} t WHERE {match})"
            )
        else:
            # Tablas con llave primaria natural: el registro nuevo reemplaza al anterior
            conn.execute(
                f"INSERT OR REPLACE INTO {target.table} ({insert_cols}) "
                f"SELECT {insert_cols} FROM {staging}"
            )
        conn.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
    except sqlite3.DatabaseError:
        conn.rollback()
        conn.execute(f"DROP TABLE IF EXISTS {staging}")
        raise

    after = conn.execute(f"SELECT COUNT(*) FROM {target.table}").fetchone()[0]
    inserted = after - before
    load_seconds = round(time.perf_counter() - started, 2)

    refresh = refresh_materialized(conn)
    logger.info("Carga %s -> %s: %s filas nuevas", file_name, target.table, inserted)

    return {
        "type": upload_type,
        "table": target.table,
        "fileName": file_name,
        "rowsRead": int(len(raw)),
        "rowsAfterCleaning": int(len(clean)),
        "rowsInserted": int(inserted),
        "rowsUpdatedOrSkipped": int(len(clean) - inserted),
        "totalRowsInTable": int(after),
        "ignoredColumns": ignored_columns,
        "loadSeconds": load_seconds,
        "semanticLayerRefresh": refresh,
    }
