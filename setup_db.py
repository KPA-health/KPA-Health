"""
Carga inicial: construye hospital.db a partir de los archivos planos de data/.

Uso:
    python setup_db.py

Este script es solo un punto de entrada de línea de comandos. El esquema vive en
backend/models/his_schema.py y la lectura/limpieza con Pandas en
backend/services/file_processing/dataframe_cleaner.py, que son los mismos módulos
que usa POST /api/upload/{type}: una carga incremental aplica exactamente la
misma limpieza que la carga inicial.

La capa semántica (vistas y tablas derivadas) la construye el backend al arrancar.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from backend.core.config import PROJECT_ROOT, get_settings
from backend.models.his_schema import create_schema
from backend.services.file_processing.dataframe_cleaner import load_directory

DATA_DIR = PROJECT_ROOT / "data"


def main() -> int:
    """Recrea las tablas del HIS y carga los archivos de data/. Devuelve el código de salida."""
    db_path: Path = get_settings().database_path
    conn = sqlite3.connect(db_path)
    try:
        print("1. Construyendo la arquitectura relacional (tablas y llaves)...")
        create_schema(conn)
        print("\n2. Iniciando limpieza e inyección de datos...")
        inserted = load_directory(conn, DATA_DIR)
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        print(f"\nError durante la carga: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    for table, rows in inserted.items():
        print(f"   ✔️ {table}: {rows} registros insertados.")
    print(f"\n¡Operación exitosa! Base de datos creada en {db_path}.")
    print("La capa semántica (vistas y tablas derivadas) la construye el backend al arrancar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
