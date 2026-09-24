"""Controlador de médicos: /doctors (contrato de frontend/js/services/doctorService.js)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.controllers.dependencies import require_permission
from backend.models import doctor_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse, ListResponse
from backend.schemas.resources import Doctor, DoctorUpdate
from backend.services.auth.permissions import PERM_OPERATIONS

router = APIRouter(prefix="/doctors", tags=["Médicos"])


@router.get("", response_model=ListResponse[Doctor])
def list_doctors(specialty: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    data = doctor_model.list_doctors(conn, specialty)
    return ListResponse[Doctor](data=data, count=len(data))


@router.get("/{doctor_id}", response_model=ItemResponse[Doctor])
def get_doctor(doctor_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Doctor](data=doctor_model.get_doctor(conn, doctor_id))


@router.put("/{doctor_id}", response_model=ItemResponse[Doctor],
            dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_doctor(doctor_id: str, payload: DoctorUpdate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Doctor](data=doctor_model.update_doctor(conn, doctor_id, payload),
                                message="Estado del médico actualizado")
