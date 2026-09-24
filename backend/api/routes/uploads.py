"""
POST /api/upload/{type} — carga de archivos del HIS.

Contrato de MediPulse.DataSync.uploadFile (index.html): FormData con el campo
`file` y `type` en {paciente, triage, ingresos, atencion, medicamento, servicios, cirugia}.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.errors import ValidationError
from backend.etl.ingestion import UPLOAD_TARGETS, ingest_file

router = APIRouter(tags=["Carga de datos"])

ALLOWED_EXTENSIONS = {".txt", ".csv"}


@router.get("/upload/types")
def upload_types():
    return {"data": {key: target.table for key, target in UPLOAD_TARGETS.items()}}


@router.post("/upload/{upload_type}")
def upload_file(
    upload_type: str,
    file: UploadFile = File(..., description="Archivo plano del HIS separado por '|'"),
    conn: sqlite3.Connection = Depends(get_db),
):
    name = file.filename or "archivo"
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError("Solo se aceptan archivos .txt o .csv separados por '|'")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise ValidationError(f"El archivo supera el máximo de {get_settings().max_upload_mb} MB")

    summary = ingest_file(conn, upload_type, file.file, name)
    return {
        "success": True,
        "message": (
            f"Base de datos de {upload_type} actualizada: {summary['rowsInserted']} registros nuevos "
            f"en {summary['table']}"
        ),
        "data": summary,
    }
