"""/patients — contrato de hospital-spa/js/services/patientService.js."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.permissions import PERM_OPERATIONS
from backend.core.database import get_db
from backend.repositories import patients as repo
from backend.schemas.common import ItemResponse, ListResponse, SuccessResponse
from backend.schemas.patients import Patient, PatientCreate, PatientUpdate

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
    data, total = repo.list_patients(conn, q, status, department, triage, limit, offset)
    return ListResponse[Patient](data=data, count=total)


@router.get("/{patient_id}", response_model=ItemResponse[Patient])
def get_patient(patient_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Patient](data=repo.get_patient(conn, patient_id))


@router.post("", response_model=ItemResponse[Patient], status_code=201)
def create_patient(payload: PatientCreate, conn: sqlite3.Connection = Depends(get_db)):
    patient = repo.create_patient(conn, payload)
    return ItemResponse[Patient](data=patient, message="Paciente registrado exitosamente")


@router.put("/{patient_id}", response_model=ItemResponse[Patient])
def update_patient(patient_id: str, payload: PatientUpdate, conn: sqlite3.Connection = Depends(get_db)):
    patient = repo.update_patient(conn, patient_id, payload)
    return ItemResponse[Patient](data=patient, message="Datos del paciente actualizados")


@router.delete("/{patient_id}", response_model=SuccessResponse,
               dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def delete_patient(patient_id: str, conn: sqlite3.Connection = Depends(get_db)):
    repo.delete_patient(conn, patient_id)
    return SuccessResponse(message="Registro de paciente eliminado")
