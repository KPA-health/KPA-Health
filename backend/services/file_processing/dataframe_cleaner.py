"""
Lectura y limpieza de los archivos planos del HIS con Pandas.

Única fuente de verdad del ETL: la carga inicial (setup_db.py) y la carga
incremental por la API (ingestion_service.py) usan exactamente estas funciones,
de modo que un archivo subido desde la interfaz queda igual de limpio que uno
cargado al construir la base de datos.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import IO

import pandas as pd

from backend.models.his_schema import LOAD_ORDER, TEXT_DECLARED_TYPES, get_declared_types

logger = logging.getLogger("medipulse.etl")

SOURCE_SEPARATOR = "|"
SOURCE_ENCODING = "utf-8"
# Representaciones de "vacío" que llegan en los extractos y se unifican
MISSING_TEXT_TOKENS = ["nan", "NaN", "None", "", "NaT"]
MISSING_TEXT_VALUE = "No Registrado"


def is_text_column(series: pd.Series, declared_type: str = "") -> bool:
    """
    True si la columna es de texto: por su tipo en pandas 2 (object) o pandas 3 (str),
    o por el tipo declarado en el esquema. Lo segundo cubre columnas de texto que
    llegan completamente vacías y que pandas infiere como numéricas.
    """
    return (
        declared_type in TEXT_DECLARED_TYPES
        or pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    )


def read_source_file(source: str | Path | IO[bytes], nrows: int | None = None) -> pd.DataFrame:
    """Lee un archivo plano del HIS (separado por '|'). Acepta una ruta o un buffer binario."""
    return pd.read_csv(source, sep=SOURCE_SEPARATOR, encoding=SOURCE_ENCODING, low_memory=False, nrows=nrows)


def clean_dataframe(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """
    Limpieza estándar + reglas específicas por tabla. Devuelve un DataFrame nuevo.

    - Quita duplicados exactos y espacios en los nombres de columna.
    - Texto: vacíos -> 'No Registrado' (el agente NL2SQL y la API cuentan con ese marcador).
    - Números: vacíos -> 0.
    - Paciente: anonimización; el nombre real NUNCA entra a la base de datos.
    """
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = df.drop_duplicates()
    declared_types = get_declared_types(table_name)

    for column in df.columns:
        if is_text_column(df[column], declared_types.get(column, "")):
            # fillna explícito: en pandas 3 astype(str) conserva los NaN
            df[column] = df[column].fillna(MISSING_TEXT_VALUE).astype(str).str.strip()
            df[column] = df[column].replace(MISSING_TEXT_TOKENS, MISSING_TEXT_VALUE)
        else:
            df[column] = df[column].fillna(0)

    if table_name == "Paciente":
        df["NombrePaciente"] = "Paciente_" + df["IdPaciente"].astype(str)
        df["FechaNacimiento"] = pd.to_datetime(df["FechaNacimiento"], errors="coerce")
    elif table_name == "Ingresos":
        df["FechaIngreso"] = pd.to_datetime(df["FechaIngreso"], errors="coerce")
        df["FechaHospitalizacion"] = pd.to_datetime(df["FechaHospitalizacion"], errors="coerce")

    return df


def load_directory(
    conn: sqlite3.Connection,
    data_dir: str | Path,
    row_limits: dict[str, int] | None = None,
) -> dict[str, int]:
    """
    Lee, limpia e inserta cada `<Tabla>.txt` de `data_dir` en su tabla (ya creada).

    `row_limits` permite cargar solo una muestra por tabla (lo usan las pruebas).
    Devuelve {tabla: filas insertadas}; las tablas sin archivo se omiten con un aviso.
    """
    inserted: dict[str, int] = {}
    for table in LOAD_ORDER:
        path = Path(data_dir) / f"{table}.txt"
        if not path.exists():
            logger.warning("Archivo no encontrado: %s", path)
            continue
        df = clean_dataframe(read_source_file(path, nrows=(row_limits or {}).get(table)), table)
        # if_exists="append" respeta el esquema relacional creado por his_schema.create_schema
        df.to_sql(table, conn, if_exists="append", index=False)
        inserted[table] = len(df)
    return inserted
