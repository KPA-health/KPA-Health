"""Repositorios de médicos (/doctors) y citas (/appointments). Tablas operativas Medico y Cita."""
from __future__ import annotations

import sqlite3

from backend.core.errors import NotFoundError
from backend.core.timeutils import now_str
from backend.schemas.resources import (
    Appointment, AppointmentCreate, AppointmentUpdate, Doctor, DoctorUpdate,
)

# ------------------------------- Médicos -------------------------------------


def _to_doctor(row: sqlite3.Row) -> Doctor:
    return Doctor(
        id=row["IdMedico"], name=row["Nombre"], specialty=row["Especialidad"],
        department=row["Departamento"], license_number=row["RegistroProfesional"],
        shift=row["Turno"], status=row["Estado"], phone=row["Telefono"], email=row["Email"],
        consulting_room=row["Consultorio"], avatar=row["Avatar"],
    )


def list_doctors(conn: sqlite3.Connection, specialty: str | None = None) -> list[Doctor]:
    if specialty and specialty != "all":
        rows = conn.execute(
            "SELECT * FROM Medico WHERE Especialidad = ? ORDER BY Nombre", (specialty,)
        )
    else:
        rows = conn.execute("SELECT * FROM Medico ORDER BY Nombre")
    return [_to_doctor(r) for r in rows]


def get_doctor(conn: sqlite3.Connection, doctor_id: str) -> Doctor:
    row = conn.execute("SELECT * FROM Medico WHERE IdMedico = ?", (doctor_id,)).fetchone()
    if row is None:
        raise NotFoundError("Doctor no encontrado")
    return _to_doctor(row)


def update_doctor(conn: sqlite3.Connection, doctor_id: str, data: DoctorUpdate) -> Doctor:
    get_doctor(conn, doctor_id)
    columns = {
        "status": "Estado", "shift": "Turno", "consulting_room": "Consultorio",
        "phone": "Telefono", "email": "Email",
    }
    updates = {columns[k]: v for k, v in data.model_dump(exclude_unset=True).items() if k in columns}
    if updates:
        assignments = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE Medico SET {assignments} WHERE IdMedico = ?", (*updates.values(), doctor_id)
        )
        conn.commit()
    return get_doctor(conn, doctor_id)


# -------------------------------- Citas --------------------------------------

_APPOINTMENT_COLUMNS = {
    "patient_id": "IdPacienteApp", "patient_name": "NombrePaciente", "doctor_id": "IdMedico",
    "doctor_name": "NombreMedico", "specialty": "Especialidad", "date": "Fecha", "time": "Hora",
    "reason": "Motivo", "status": "Estado", "priority": "Prioridad",
}


def _to_appointment(row: sqlite3.Row) -> Appointment:
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
    return [_to_appointment(r) for r in rows]


def get_appointment(conn: sqlite3.Connection, appointment_id: str) -> Appointment:
    row = conn.execute("SELECT * FROM Cita WHERE IdCita = ?", (appointment_id,)).fetchone()
    if row is None:
        raise NotFoundError("Cita médica no encontrada")
    return _to_appointment(row)


def create_appointment(conn: sqlite3.Connection, data: AppointmentCreate) -> Appointment:
    next_number = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(IdCita, 5) AS INTEGER)), 500) + 1 FROM Cita "
        "WHERE IdCita LIKE 'APT-%'"
    ).fetchone()[0]
    appointment_id = f"APT-{next_number}"
    values = data.model_dump()
    # Privacidad: el nombre del paciente nunca se guarda, solo un seudónimo
    values["patient_name"] = f"Paciente {data.patient_id}" if data.patient_id else "Paciente anónimo"
    values["status"] = values.get("status") or "Programada"
    values["priority"] = values.get("priority") or "Normal"
    columns = ["IdCita", *(_APPOINTMENT_COLUMNS[k] for k in _APPOINTMENT_COLUMNS), "CreadoEn"]
    params = [appointment_id, *(values.get(k) for k in _APPOINTMENT_COLUMNS), now_str()]
    conn.execute(
        f"INSERT INTO Cita ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})", params
    )
    conn.commit()
    return get_appointment(conn, appointment_id)


def update_appointment(
    conn: sqlite3.Connection, appointment_id: str, data: AppointmentUpdate
) -> Appointment:
    get_appointment(conn, appointment_id)
    fields = data.model_dump(exclude_unset=True)
    fields.pop("patient_name", None)  # nunca se guardan nombres de pacientes
    if fields.get("patient_id"):
        fields["patient_name"] = f"Paciente {fields['patient_id']}"
    updates = {_APPOINTMENT_COLUMNS[k]: v for k, v in fields.items() if k in _APPOINTMENT_COLUMNS}
    if updates:
        assignments = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE Cita SET {assignments} WHERE IdCita = ?", (*updates.values(), appointment_id)
        )
        conn.commit()
    return get_appointment(conn, appointment_id)


def delete_appointment(conn: sqlite3.Connection, appointment_id: str) -> None:
    get_appointment(conn, appointment_id)
    conn.execute("DELETE FROM Cita WHERE IdCita = ?", (appointment_id,))
    conn.commit()
