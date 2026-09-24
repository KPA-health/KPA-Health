"""
Modelo de médicos (capa Modelo): tabla operativa Medico para /doctors.

El extracto del HIS no trae personal médico: la tabla se siembra con datos demo
(ver seed_data.py) para que el módulo de médicos del frontend funcione contra la API.
"""
from __future__ import annotations

import sqlite3

from backend.core.errors import NotFoundError
from backend.schemas.resources import Doctor, DoctorUpdate

# Campos editables del DTO -> columnas de la tabla Medico
_EDITABLE_COLUMNS = {
    "status": "Estado", "shift": "Turno", "consulting_room": "Consultorio",
    "phone": "Telefono", "email": "Email",
}


def _to_doctor(row: sqlite3.Row) -> Doctor:
    """Fila de Medico -> DTO Doctor."""
    return Doctor(
        id=row["IdMedico"], name=row["Nombre"], specialty=row["Especialidad"],
        department=row["Departamento"], license_number=row["RegistroProfesional"],
        shift=row["Turno"], status=row["Estado"], phone=row["Telefono"], email=row["Email"],
        consulting_room=row["Consultorio"], avatar=row["Avatar"],
    )


def list_doctors(conn: sqlite3.Connection, specialty: str | None = None) -> list[Doctor]:
    """Médicos ordenados por nombre, opcionalmente filtrados por especialidad ('all' = sin filtro)."""
    if specialty and specialty != "all":
        rows = conn.execute("SELECT * FROM Medico WHERE Especialidad = ? ORDER BY Nombre", (specialty,))
    else:
        rows = conn.execute("SELECT * FROM Medico ORDER BY Nombre")
    return [_to_doctor(row) for row in rows]


def get_doctor(conn: sqlite3.Connection, doctor_id: str) -> Doctor:
    """Un médico por id o NotFoundError."""
    row = conn.execute("SELECT * FROM Medico WHERE IdMedico = ?", (doctor_id,)).fetchone()
    if row is None:
        raise NotFoundError("Doctor no encontrado")
    return _to_doctor(row)


def update_doctor(conn: sqlite3.Connection, doctor_id: str, data: DoctorUpdate) -> Doctor:
    """Actualiza solo los campos enviados (estado, turno, consultorio, contacto)."""
    get_doctor(conn, doctor_id)
    updates = {
        _EDITABLE_COLUMNS[field]: value
        for field, value in data.model_dump(exclude_unset=True).items()
        if field in _EDITABLE_COLUMNS
    }
    if updates:
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(f"UPDATE Medico SET {assignments} WHERE IdMedico = ?", (*updates.values(), doctor_id))
        conn.commit()
    return get_doctor(conn, doctor_id)
