"""
Carga incremental de archivos del HIS (POST /api/upload/{type}).

Reutiliza la misma lectura y limpieza de la carga inicial (dataframe_cleaner.py)
y agrega lo que una carga repetible necesita: validación de columnas, tabla de
staging e inserción idempotente (volver a subir el mismo archivo no duplica registros).

Flujo: leer (Pandas) -> alinear columnas -> limpiar -> staging -> INSERT sin
duplicados en una transacción -> recalcular la capa semántica.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import IO

import pandas as pd

from backend.core.errors import BadRequestError
from backend.models.his_schema import AUTOINCREMENT_COLUMNS, get_table_columns
from backend.models.semantic_layer import refresh_materialized
from backend.services.file_processing.dataframe_cleaner import clean_dataframe, read_source_file

logger = logging.getLogger("medipulse.etl")


@dataclass(frozen=True)
class UploadTarget:
    """Tabla destino de un tipo de carga."""
    table: str
    # Clave natural usada para no duplicar filas en tablas con id autoincremental
    natural_key: tuple[str, ...] | None = None


# Tipos que envía el frontend (MediPulse.DataSync.uploadFile) -> tabla del HIS.
# Las claves son valores del contrato con la SPA (ids del HTML), no identificadores de código.
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

# Alias tolerados: plurales, nombres de tabla y equivalentes en inglés
_ALIASES = {
    "pacientes": "paciente", "ingreso": "ingresos", "atenciones": "atencion",
    "medicamentos": "medicamento", "medicamentoinsumo": "medicamento", "farmacia": "medicamento",
    "servicio": "servicios", "cirugias": "cirugia", "programacioncirugia": "cirugia",
    "patient": "paciente", "patients": "paciente", "admission": "ingresos", "admissions": "ingresos",
    "care": "atencion", "medication": "medicamento", "medications": "medicamento",
    "services": "servicios", "surgery": "cirugia", "surgeries": "cirugia",
}


def resolve_target(upload_type: str) -> UploadTarget:
    """Tipo de carga (o alias) -> tabla destino; 400 si el tipo no está soportado."""
    key = upload_type.strip().lower()
    key = _ALIASES.get(key, key)
    if key not in UPLOAD_TARGETS:
        raise BadRequestError(
            f"Tipo de carga no soportado: '{upload_type}'",
            {"supportedTypes": sorted(UPLOAD_TARGETS)},
        )
    return UPLOAD_TARGETS[key]


def _align_columns(df: pd.DataFrame, table_columns: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    Deja solo las columnas de la tabla, en su orden. Falla si falta alguna (así un
    archivo equivocado no se inserta a medias) y reporta las columnas ignoradas.
    """
    expected = [c for c in table_columns if c not in AUTOINCREMENT_COLUMNS]
    received = [c.strip() for c in df.columns]
    missing = [c for c in expected if c not in received]
    if missing:
        raise BadRequestError(
            "El archivo no tiene las columnas esperadas para esta tabla",
            {"missingColumns": missing, "expectedColumns": expected, "receivedColumns": received},
        )
    ignored = [c for c in received if c not in expected]
    return df[expected], ignored


def ingest_file(
    conn: sqlite3.Connection, upload_type: str, file_obj: IO[bytes], file_name: str
) -> dict:
    """
    Inserta el contenido de un archivo del HIS en su tabla y devuelve un resumen de la carga.

    Idempotencia: las tablas con llave primaria natural usan INSERT OR REPLACE; las
    que tienen id autoincremental comparan contra `natural_key` para no duplicar.
    Todo ocurre en una transacción: si algo falla, la tabla queda como estaba.
    """
    target = resolve_target(upload_type)
    started = time.perf_counter()

    try:
        raw = read_source_file(file_obj)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise BadRequestError(f"No se pudo leer el archivo '{file_name}': {exc}") from exc

    raw.columns = raw.columns.str.strip()
    raw, ignored_columns = _align_columns(raw, get_table_columns(conn, target.table))
    clean = clean_dataframe(raw, target.table)
    if clean.empty:
        raise BadRequestError(f"El archivo '{file_name}' no contiene registros")

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
        logger.exception("Falló la carga de %s en %s", file_name, target.table)
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
