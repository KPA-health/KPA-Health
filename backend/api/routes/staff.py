"""/doctors y /appointments — contratos de doctorService.js y appointmentService.js."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.permissions import PERM_OPERATIONS
from backend.core.database import get_db
from backend.repositories import staff as repo
from backend.schemas.common import ItemResponse, ListResponse, SuccessResponse
from backend.schemas.resources import (
    Appointment, AppointmentCreate, AppointmentUpdate, Doctor, DoctorUpdate,
)

doctors_router = APIRouter(prefix="/doctors", tags=["Médicos"])
appointments_router = APIRouter(prefix="/appointments", tags=["Citas"])


@doctors_router.get("", response_model=ListResponse[Doctor])
def list_doctors(specialty: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    data = repo.list_doctors(conn, specialty)
    return ListResponse[Doctor](data=data, count=len(data))


@doctors_router.get("/{doctor_id}", response_model=ItemResponse[Doctor])
def get_doctor(doctor_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Doctor](data=repo.get_doctor(conn, doctor_id))


@doctors_router.put("/{doctor_id}", response_model=ItemResponse[Doctor],
                    dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_doctor(doctor_id: str, payload: DoctorUpdate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Doctor](data=repo.update_doctor(conn, doctor_id, payload),
                                message="Estado del médico actualizado")


@appointments_router.get("", response_model=ListResponse[Appointment])
def list_appointments(
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    status: str | None = None,
    doctor_id: str | None = Query(default=None, alias="doctorId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    data = repo.list_appointments(conn, date, status, doctor_id)
    return ListResponse[Appointment](data=data, count=len(data))


@appointments_router.get("/{appointment_id}", response_model=ItemResponse[Appointment])
def get_appointment(appointment_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Appointment](data=repo.get_appointment(conn, appointment_id))


@appointments_router.post("", response_model=ItemResponse[Appointment], status_code=201)
def create_appointment(payload: AppointmentCreate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Appointment](data=repo.create_appointment(conn, payload),
                                     message="Cita médica agendada correctamente")


@appointments_router.patch("/{appointment_id}", response_model=ItemResponse[Appointment])
@appointments_router.put("/{appointment_id}", response_model=ItemResponse[Appointment])
def update_appointment(
    appointment_id: str, payload: AppointmentUpdate, conn: sqlite3.Connection = Depends(get_db)
):
    return ItemResponse[Appointment](data=repo.update_appointment(conn, appointment_id, payload),
                                     message="Cita médica actualizada")


@appointments_router.delete("/{appointment_id}", response_model=SuccessResponse)
def delete_appointment(appointment_id: str, conn: sqlite3.Connection = Depends(get_db)):
    repo.delete_appointment(conn, appointment_id)
    return SuccessResponse(message="Cita médica eliminada")
