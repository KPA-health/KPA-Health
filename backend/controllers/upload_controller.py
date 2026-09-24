"""
Controlador de carga de archivos del HIS: POST /api/upload/{type}.

Contrato de MediPulse.DataSync.uploadFile (frontend): FormData con el campo
`file` y `type` en {paciente, triage, ingresos, atencion, medicamento, servicios, cirugia}.

El controlador valida lo que depende de HTTP (extensión y tamaño del archivo) y
delega la lectura, limpieza e inserción en services/file_processing.
"""
from __future__ import annotations

import sqlite3
import os
import codecs
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, UploadFile

from backend.core.config import get_settings
from backend.core.errors import BadRequestError, PayloadTooLargeError
from backend.models.db_connection import get_db
from backend.services.file_processing.ingestion_service import UPLOAD_TARGETS, ingest_file

router = APIRouter(tags=["Carga de datos"])

ALLOWED_EXTENSIONS = {".txt", ".csv"}
ALLOWED_MIME_TYPES = {"text/plain", "text/csv", "application/csv", "application/vnd.ms-excel"}
BYTES_PER_MB = 1024 * 1024


@router.get("/upload/types")
def list_upload_types():
    """Tipos de carga soportados y la tabla del HIS que alimenta cada uno."""
    return {"data": {key: target.table for key, target in UPLOAD_TARGETS.items()}}


def _validate_upload(file: UploadFile) -> str:
    """Valida extensión y tamaño antes de leer el archivo; devuelve el nombre a reportar."""
    file_name = file.filename or "archivo"
    decoded = file_name
    for _ in range(3):
        decoded = unquote(decoded)
    if (decoded != os.path.basename(decoded) or "\\" in decoded or ".." in decoded
            or "/" in decoded or any(ord(char) < 32 for char in decoded)):
        raise BadRequestError("Nombre de archivo no permitido")
    if Path(file_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise BadRequestError("Solo se aceptan archivos .txt o .csv separados por '|'")
    if (file.content_type or "").lower().split(";", 1)[0].strip() not in ALLOWED_MIME_TYPES:
        raise BadRequestError("Tipo MIME no permitido para archivos .txt o .csv")
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
        max_bytes = get_settings().max_upload_mb * BYTES_PER_MB
        with tempfile.TemporaryDirectory(prefix="medipulse-upload-") as isolated:
            safe_path = Path(isolated).resolve() / f"{uuid.uuid4().hex}{Path(file_name).suffix.lower()}"
            if safe_path.parent != Path(isolated).resolve():
                raise BadRequestError("Ruta de archivo no permitida")
            total = 0
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            with safe_path.open("xb") as output:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise PayloadTooLargeError(f"El archivo supera el máximo de {get_settings().max_upload_mb} MB")
                    if re.search(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", chunk):
                        raise BadRequestError("El archivo debe ser texto plano")
                    try:
                        decoder.decode(chunk)
                    except UnicodeDecodeError as exc:
                        raise BadRequestError("El archivo debe ser texto UTF-8") from exc
                    output.write(chunk)
                try:
                    decoder.decode(b"", final=True)
                except UnicodeDecodeError as exc:
                    raise BadRequestError("El archivo debe ser texto UTF-8") from exc
            with safe_path.open("rb") as source:
                summary = ingest_file(conn, upload_type, source, file_name)
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
