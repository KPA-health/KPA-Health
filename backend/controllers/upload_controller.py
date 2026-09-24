"""
Controlador de carga de archivos del HIS: POST /api/upload/{type}.

Contrato de MediPulse.DataSync.uploadFile (frontend): FormData con el campo
`file` y `type` en {paciente, triage, ingresos, atencion, medicamento, servicios, cirugia}.

El controlador valida lo que depende de HTTP (extensión y tamaño del archivo) y
delega la lectura, limpieza e inserción en services/file_processing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from backend.core.config import get_settings
from backend.core.errors import BadRequestError, PayloadTooLargeError
from backend.models.db_connection import get_db
from backend.services.file_processing.ingestion_service import UPLOAD_TARGETS, ingest_file

router = APIRouter(tags=["Carga de datos"])

ALLOWED_EXTENSIONS = {".txt", ".csv"}
BYTES_PER_MB = 1024 * 1024


@router.get("/upload/types")
def list_upload_types():
    """Tipos de carga soportados y la tabla del HIS que alimenta cada uno."""
    return {"data": {key: target.table for key, target in UPLOAD_TARGETS.items()}}


def _validate_upload(file: UploadFile) -> str:
    """Valida extensión y tamaño antes de leer el archivo; devuelve el nombre a reportar."""
    file_name = file.filename or "archivo"
    if Path(file_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise BadRequestError("Solo se aceptan archivos .txt o .csv separados por '|'")
    max_mb = get_settings().max_upload_mb
    if file.size is not None and file.size > max_mb * BYTES_PER_MB:
        raise PayloadTooLargeError(f"El archivo supera el máximo de {max_mb} MB")
    return file_name


@router.post("/upload/{upload_type}")
def upload_file(
    upload_type: str,
    file: UploadFile = File(..., description="Archivo plano del HIS separado por '|'"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Inserta el archivo en su tabla (idempotente) y recalcula la capa semántica."""
    try:
        file_name = _validate_upload(file)
        summary = ingest_file(conn, upload_type, file.file, file_name)
    finally:
        # El archivo temporal de Starlette se libera aunque la carga falle
        file.file.close()
    return {
        "success": True,
        "message": (
            f"Base de datos de {upload_type} actualizada: {summary['rowsInserted']} registros nuevos "
            f"en {summary['table']}"
        ),
        "data": summary,
    }
