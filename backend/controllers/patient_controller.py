"""Controlador de pacientes: /patients (contrato de front-kpa/js/services/patientService.js)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.controllers.dependencies import require_permission
from backend.models import patient_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse, ListResponse, SuccessResponse
from backend.schemas.patients import Patient, PatientCreate, PatientUpdate
from backend.services.auth.permissions import PERM_OPERATIONS

router = APIRouter(prefix="/patients", tags=["Pacientes"])


@router.get("", response_model=ListResponse[Patient], response_model_by_alias=True)
def list_patients(
    q: str | None = Query(default=None, description="Busca en id, nombre, documento o diagnóstico"),
    status: str | None = Query(default=None, description="Estado o 'active' para hospitalizados"),
    department: str | None = Query(default=None, description="Servicio (ej. 'Cuidados Intensivos (UCI)')"),
    triage: str | None = Query(default=None, description="Nivel de triage 1-5"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Listado paginado; `count` es el total de coincidencias (no solo la página)."""
    data, total = patient_model.list_patients(conn, q, status, department, triage, limit, offset)
    return ListResponse[Patient](data=data, count=total)


@router.get("/{patient_id}", response_model=ItemResponse[Patient])
def get_patient(patient_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Patient](data=patient_model.get_patient(conn, patient_id))


@router.post("", response_model=ItemResponse[Patient], status_code=201)
def create_patient(payload: PatientCreate, conn: sqlite3.Connection = Depends(get_db)):
    """Registro desde el wizard. 409 si la cama elegida ya no está libre."""
    patient = patient_model.create_patient(conn, payload)
    return ItemResponse[Patient](data=patient, message="Paciente registrado exitosamente")


@router.put("/{patient_id}", response_model=ItemResponse[Patient])
def update_patient(patient_id: str, payload: PatientUpdate, conn: sqlite3.Connection = Depends(get_db)):
    patient = patient_model.update_patient(conn, patient_id, payload)
    return ItemResponse[Patient](data=patient, message="Datos del paciente actualizados")


@router.delete("/{patient_id}", response_model=SuccessResponse,
               dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def delete_patient(patient_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """Borrado lógico (solo administradores): el registro del HIS se conserva."""
    patient_model.delete_patient(conn, patient_id)
    return SuccessResponse(message="Registro de paciente eliminado")
