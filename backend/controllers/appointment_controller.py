"""Controlador de citas: /appointments (contrato de front-kpa/js/services/appointmentService.js)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.models import appointment_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse, ListResponse, SuccessResponse
from backend.schemas.resources import Appointment, AppointmentCreate, AppointmentUpdate

router = APIRouter(prefix="/appointments", tags=["Citas"])


@router.get("", response_model=ListResponse[Appointment])
def list_appointments(
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    status: str | None = None,
    doctor_id: str | None = Query(default=None, alias="doctorId"),
    conn: sqlite3.Connection = Depends(get_db),
):
    data = appointment_model.list_appointments(conn, date, status, doctor_id)
    return ListResponse[Appointment](data=data, count=len(data))


@router.get("/{appointment_id}", response_model=ItemResponse[Appointment])
def get_appointment(appointment_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Appointment](data=appointment_model.get_appointment(conn, appointment_id))


@router.post("", response_model=ItemResponse[Appointment], status_code=201)
def create_appointment(payload: AppointmentCreate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Appointment](data=appointment_model.create_appointment(conn, payload),
                                     message="Cita médica agendada correctamente")


# El frontend usa PATCH para cambiar el estado y PUT para editar la cita completa
@router.patch("/{appointment_id}", response_model=ItemResponse[Appointment])
@router.put("/{appointment_id}", response_model=ItemResponse[Appointment])
def update_appointment(appointment_id: str, payload: AppointmentUpdate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Appointment](data=appointment_model.update_appointment(conn, appointment_id, payload),
                                     message="Cita médica actualizada")


@router.delete("/{appointment_id}", response_model=SuccessResponse)
def delete_appointment(appointment_id: str, conn: sqlite3.Connection = Depends(get_db)):
    appointment_model.delete_appointment(conn, appointment_id)
    return SuccessResponse(message="Cita médica eliminada")
