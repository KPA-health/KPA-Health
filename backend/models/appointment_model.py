"""
Modelo de citas médicas (capa Modelo): tabla operativa Cita para /appointments.

Privacidad: el nombre del paciente que envía el formulario NUNCA se guarda; la
cita conserva solo un seudónimo derivado del id del paciente.
"""
from __future__ import annotations

import sqlite3

from backend.core.errors import NotFoundError
from backend.core.time_utils import now_str
from backend.schemas.resources import Appointment, AppointmentCreate, AppointmentUpdate

# Campos del DTO -> columnas de la tabla Cita
_APPOINTMENT_COLUMNS = {
    "patient_id": "IdPacienteApp", "patient_name": "NombrePaciente", "doctor_id": "IdMedico",
    "doctor_name": "NombreMedico", "specialty": "Especialidad", "date": "Fecha", "time": "Hora",
    "reason": "Motivo", "status": "Estado", "priority": "Prioridad",
}
ID_PREFIX = "APT-"
# Las citas demo usan APT-501...; las nuevas continúan la numeración
FIRST_APPOINTMENT_NUMBER = 500


def _pseudonym(patient_id: str | None) -> str:
    return f"Paciente {patient_id}" if patient_id else "Paciente anónimo"


def _to_appointment(row: sqlite3.Row) -> Appointment:
    """Fila de Cita -> DTO Appointment."""
    return Appointment(
        id=row["IdCita"], patient_id=row["IdPacienteApp"], patient_name=row["NombrePaciente"],
        doctor_id=row["IdMedico"], doctor_name=row["NombreMedico"], specialty=row["Especialidad"],
        date=row["Fecha"], time=row["Hora"], reason=row["Motivo"], status=row["Estado"],
        priority=row["Prioridad"],
    )


def list_appointments(
    conn: sqlite3.Connection,
    date: str | None = None,
    status: str | None = None,
    doctor_id: str | None = None,
) -> list[Appointment]:
    """Agenda filtrada por fecha, estado y médico, ordenada cronológicamente."""
    where, params = [], []
    if date:
        where.append("Fecha = ?")
        params.append(date)
    if status and status != "all":
        where.append("Estado = ?")
        params.append(status)
    if doctor_id and doctor_id != "all":
        where.append("IdMedico = ?")
        params.append(doctor_id)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(f"SELECT * FROM Cita{clause} ORDER BY Fecha, Hora", params)
    return [_to_appointment(row) for row in rows]


def get_appointment(conn: sqlite3.Connection, appointment_id: str) -> Appointment:
    """Una cita por id o NotFoundError."""
    row = conn.execute("SELECT * FROM Cita WHERE IdCita = ?", (appointment_id,)).fetchone()
    if row is None:
        raise NotFoundError("Cita médica no encontrada")
    return _to_appointment(row)


def create_appointment(conn: sqlite3.Connection, data: AppointmentCreate) -> Appointment:
    """Agenda una cita con id consecutivo 'APT-<n>' y estado/prioridad por defecto."""
    next_number = conn.execute(
        f"SELECT COALESCE(MAX(CAST(SUBSTR(IdCita, {len(ID_PREFIX) + 1}) AS INTEGER)), ?) + 1 "
        "FROM Cita WHERE IdCita LIKE ?",
        (FIRST_APPOINTMENT_NUMBER, f"{ID_PREFIX}%"),
    ).fetchone()[0]
    appointment_id = f"{ID_PREFIX}{next_number}"
    values = data.model_dump()
    values["patient_name"] = _pseudonym(data.patient_id)
    values["status"] = values.get("status") or "Programada"
    values["priority"] = values.get("priority") or "Normal"
    columns = ["IdCita", *_APPOINTMENT_COLUMNS.values(), "CreadoEn"]
    params = [appointment_id, *(values.get(field) for field in _APPOINTMENT_COLUMNS), now_str()]
    conn.execute(
        f"INSERT INTO Cita ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})", params
    )
    conn.commit()
    return get_appointment(conn, appointment_id)


def update_appointment(conn: sqlite3.Connection, appointment_id: str, data: AppointmentUpdate) -> Appointment:
    """Actualización parcial; si cambia el paciente se recalcula su seudónimo."""
    get_appointment(conn, appointment_id)
    fields = data.model_dump(exclude_unset=True)
    fields.pop("patient_name", None)  # nunca se guardan nombres de pacientes
    if fields.get("patient_id"):
        fields["patient_name"] = _pseudonym(fields["patient_id"])
    updates = {_APPOINTMENT_COLUMNS[k]: v for k, v in fields.items() if k in _APPOINTMENT_COLUMNS}
    if updates:
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(f"UPDATE Cita SET {assignments} WHERE IdCita = ?", (*updates.values(), appointment_id))
        conn.commit()
    return get_appointment(conn, appointment_id)


def delete_appointment(conn: sqlite3.Connection, appointment_id: str) -> None:
    """Elimina una cita existente (404 si no existe)."""
    get_appointment(conn, appointment_id)
    conn.execute("DELETE FROM Cita WHERE IdCita = ?", (appointment_id,))
    conn.commit()
