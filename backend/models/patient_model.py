"""
Modelo de pacientes (capa Modelo): consultas y reglas de negocio de /patients.

Para el frontend un "paciente" es un ingreso hospitalario (tiene fecha de
ingreso, cama, triage y diagnóstico), por eso el id expuesto es `ING-<OidIngreso>`.
Los datos del HIS se leen de la vista VistaIngresos; los campos que el HIS no
tiene (alergias, tipo de sangre, estado manual, alta, etc.) viven en la tabla
operativa IngresoGestion.

Privacidad: el nombre que llega del formulario NUNCA se guarda (se usa el
seudónimo Paciente_<IdPaciente>) y el documento solo se guarda como HMAC
(DocumentoHash). Las respuestas siempre llevan el seudónimo y el documento
enmascarado.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from backend.core.errors import ConflictError, NotFoundError
from backend.core.privacy import hash_document, looks_like_document, mask_document, patient_pseudonym
from backend.core.time_utils import now_str, to_minutes_precision
from backend.schemas.patients import Patient, PatientCreate, PatientUpdate, Vitals

ID_PREFIX = "ING-"                 # id público de un paciente = número de ingreso del HIS
MISSING = "No Registrado"          # mismo marcador de vacío que usa la limpieza del ETL
DISCHARGED = "Dado de Alta"
DEFAULT_TRIAGE_LEVEL = 4

_BASE_SELECT = """
SELECT
    v.*,
    p.NombrePaciente, p.TipoDocumento,
    t.TensionArterial, t.FrecuenciaCardiaca, t.Temperatura,
    g.DocumentoHash, g.TipoSangre, g.Alergias, g.Telefono, g.SaturacionO2, g.Notas,
    g.MedicoAsignadoId, g.MedicoAsignadoNombre, g.FechaAlta, g.NotasAlta
FROM VistaIngresos v
LEFT JOIN Paciente p ON p.IdPaciente = v.IdPaciente
LEFT JOIN Ingresos i ON i.OidIngreso = v.OidIngreso
LEFT JOIN Triage t ON t.OidTriage = i.OidTriageA AND i.OidTriageA > 0
LEFT JOIN IngresoGestion g ON g.OidIngreso = v.OidIngreso
"""

# Campos de la API -> columnas de IngresoGestion
_MANAGEMENT_FIELDS = {
    "blood_type": "TipoSangre",
    "allergies": "Alergias",
    "notes": "Notas",
    "doctor_assigned_id": "MedicoAsignadoId",
    "doctor_assigned_name": "MedicoAsignadoNombre",
    "discharge_notes": "NotasAlta",
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #


def parse_patient_id(patient_id: str) -> int:
    """'ING-123' (o '123') -> 123. Un id mal formado se trata como 'no encontrado'."""
    raw = patient_id.strip().upper().removeprefix(ID_PREFIX)
    if not raw.isdigit():
        raise NotFoundError(f"Paciente con ID {patient_id} no encontrado")
    return int(raw)


def _clean_value(value: Any) -> str | None:
    """Normaliza los marcadores de vacío del HIS ('No Registrado', 0, 'nan') a None."""
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", MISSING, "0", "0.0", "nan"):
        return None
    return text.removesuffix(".0")


def _value_with_unit(value: Any, unit: str) -> str:
    text = _clean_value(value)
    return f"{text}{unit}" if text else MISSING


def _extract_number(value: str | None) -> str:
    """'80 lpm' -> '80' ; '37.5°C' -> '37.5'."""
    if not value:
        return MISSING
    match = re.search(r"\d+(?:[.,]\d+)?", value)
    return match.group(0).replace(",", ".") if match else MISSING


def _birth_date_for_age(age: int) -> str:
    """El formulario pide la edad, pero la BD guarda la fecha de nacimiento: se aproxima."""
    return (datetime.now() - timedelta(days=age * 365.25 + 1)).strftime("%Y-%m-%d 00:00:00")


def _row_to_patient(row: sqlite3.Row) -> Patient:
    """Fila de _BASE_SELECT -> DTO Patient (siempre con seudónimo y documento enmascarado)."""
    virtual = bool(row["CamaVirtual"])
    bed_code = row["CodigoCama"] if row["CodigoCama"] not in (None, MISSING, "0") else None
    if bed_code and not virtual:
        room = f"Cama {bed_code}"
    elif bed_code:
        room = f"Cama virtual {bed_code}"
    else:
        room = "Sin asignar"

    status = row["Estado"]
    discharge_date = row["FechaAlta"] or (row["FechaFinEstimada"] if status == DISCHARGED else None)
    return Patient(
        id=f"{ID_PREFIX}{row['OidIngreso']}",
        dni=mask_document(row["TipoDocumento"]),
        name=patient_pseudonym(row["IdPaciente"]),
        age=row["Edad"],
        gender=_clean_value(row["Sexo"]),
        blood_type=row["TipoSangre"] or MISSING,
        phone=None,  # dato personal: no se almacena ni se expone
        admission_date=to_minutes_precision(row["FechaIngreso"]),
        triage_level=row["NivelTriage"],
        status=status,
        department=row["Servicio"],
        room_number=room,
        bed_id=bed_code if not virtual else None,
        doctor_assigned_id=row["MedicoAsignadoId"],
        doctor_assigned_name=row["MedicoAsignadoNombre"],
        diagnosis=_clean_value(row["NombreDiagnostico"]) or MISSING,
        allergies=row["Alergias"] or MISSING,
        vitals=Vitals(
            bp=_clean_value(row["TensionArterial"]) or MISSING,
            hr=_value_with_unit(row["FrecuenciaCardiaca"], " lpm"),
            temp=_value_with_unit(row["Temperatura"], "°C"),
            spo2=row["SaturacionO2"] or MISSING,
        ),
        notes=row["Notas"],
        discharge_date=to_minutes_precision(discharge_date),
        discharge_notes=row["NotasAlta"],
        admission_class=row["ClaseIngreso"],
        admission_route=row["ViaIngreso"],
        main_specialty=row["EspecialidadPrincipal"],
        length_of_stay_days=row["DiasEstancia"],
        source=row["Origen"],
    )


def _get_row(conn: sqlite3.Connection, oid: int) -> sqlite3.Row:
    """Fila completa del ingreso o NotFoundError."""
    row = conn.execute(f"{_BASE_SELECT} WHERE v.OidIngreso = ?", (oid,)).fetchone()
    if row is None:
        raise NotFoundError(f"Paciente con ID {ID_PREFIX}{oid} no encontrado")
    return row


def _get_available_bed(conn: sqlite3.Connection, bed_id: str, current_oid: int | None = None) -> sqlite3.Row:
    """
    Cama del catálogo lista para asignarse. Falla con 404 si no existe y con 409 si
    está ocupada por OTRO ingreso (reasignar la cama propia no es un conflicto).
    """
    bed = conn.execute(
        "SELECT c.*, e.Estado, e.OidIngreso AS Ocupante FROM CatalogoCamas c "
        "JOIN EstadoCamas e ON e.CodigoCama = c.CodigoCama WHERE c.CodigoCama = ?",
        (bed_id,),
    ).fetchone()
    if bed is None:
        raise NotFoundError(f"La cama {bed_id} no existe en el catálogo de camas")
    if bed["Estado"] != "Libre" and bed["Ocupante"] != current_oid:
        raise ConflictError(f"La cama {bed_id} no está disponible (estado: {bed['Estado']})")
    return bed


def _upsert_management(conn: sqlite3.Connection, oid: int, values: dict[str, Any]) -> None:
    """
    Inserta o actualiza los campos operativos del ingreso en IngresoGestion.

    Las tablas del HIS se tratan como fuente de verdad de solo lectura; lo que la
    app agrega (estado manual, alergias, alta...) vive en esta tabla aparte.
    """
    values = {**values, "ActualizadoEn": now_str()}
    columns = ", ".join(["OidIngreso", *values])
    placeholders = ", ".join(["?"] * (len(values) + 1))
    updates = ", ".join(f"{col} = excluded.{col}" for col in values)
    conn.execute(
        f"INSERT INTO IngresoGestion ({columns}) VALUES ({placeholders}) "
        f"ON CONFLICT(OidIngreso) DO UPDATE SET {updates}",
        (oid, *values.values()),
    )


def _next_id(conn: sqlite3.Connection, table: str, column: str) -> int:
    """Siguiente id numérico de una tabla del HIS (sus llaves no son AUTOINCREMENT)."""
    return (conn.execute(f"SELECT COALESCE(MAX({column}), 0) + 1 FROM {table}").fetchone()[0])


# --------------------------------------------------------------------------- #
# Operaciones públicas del modelo
# --------------------------------------------------------------------------- #


def list_patients(
    conn: sqlite3.Connection,
    q: str | None = None,
    status: str | None = None,
    department: str | None = None,
    triage: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Patient], int]:
    """Lista paginada de pacientes con filtros; devuelve (página, total sin paginar)."""
    where, params = [], []
    if q:
        like = f"%{q.strip()}%"
        # El documento se busca por coincidencia exacta de su hash (nunca se guarda en claro)
        document_hash = hash_document(q) if looks_like_document(q) else "-"
        where.append(
            "(('ING-' || v.OidIngreso) LIKE ? OR p.NombrePaciente LIKE ? OR "
            "CAST(v.IdPaciente AS TEXT) LIKE ? OR g.DocumentoHash = ? OR v.NombreDiagnostico LIKE ?)"
        )
        params += [like, like, like, document_hash, like]
    if status and status != "all":
        if status == "active":
            where.append("v.Activo = 1")
        else:
            where.append("v.Estado = ?")
            params.append(status)
    if department and department != "all":
        where.append("v.Servicio = ?")
        params.append(department)
    if triage and str(triage) != "all":
        where.append("v.NivelTriage = ?")
        params.append(int(triage))

    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM ({_BASE_SELECT}{clause})", params
    ).fetchone()[0]
    rows = conn.execute(
        f"{_BASE_SELECT}{clause} ORDER BY v.Activo DESC, v.FechaIngreso DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return [_row_to_patient(r) for r in rows], total


def get_patient(conn: sqlite3.Connection, patient_id: str) -> Patient:
    """Detalle de un paciente por su id público 'ING-<OidIngreso>'."""
    return _row_to_patient(_get_row(conn, parse_patient_id(patient_id)))


def create_patient(conn: sqlite3.Connection, data: PatientCreate) -> Patient:
    """
    Registra un ingreso desde el wizard: crea Paciente + Triage + Ingreso en una sola
    transacción (todo o nada) y guarda los datos operativos en IngresoGestion.
    """
    now = now_str()
    bed = _get_available_bed(conn, data.bed_id) if data.bed_id else None
    level = data.triage_level or DEFAULT_TRIAGE_LEVEL
    vitals = data.vitals or Vitals()

    patient_id = _next_id(conn, "Paciente", "IdPaciente")
    triage_id = _next_id(conn, "Triage", "OidTriage")
    admission_id = _next_id(conn, "Ingresos", "OidIngreso")

    try:
        conn.execute(
            "INSERT INTO Paciente (IdPaciente, TipoDocumento, NombrePaciente, FechaNacimiento, Sexo, "
            "Asegurador, Regimen, Departamento, Municipio, Zona) VALUES (?, 'CC', ?, ?, ?, ?, ?, ?, ?, ?)",
            (patient_id, patient_pseudonym(patient_id),
             _birth_date_for_age(data.age) if data.age is not None else None,
             data.gender or MISSING, MISSING, MISSING, MISSING, MISSING, MISSING),
        )
        conn.execute(
            "INSERT INTO Triage (OidTriage, FechaTriage, MotivoConsulta, TensionArterial, "
            "FrecuenciaCardiaca, FrecuenciaRespiratoria, Temperatura, IdPaciente2, CodigoTriage, "
            "ClasificacionTriage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (triage_id, now, data.symptoms or MISSING, vitals.bp or MISSING, _extract_number(vitals.hr),
             MISSING, _extract_number(vitals.temp), patient_id, str(level),
             f"REGISTRO APP - TRIAGE {level}"),
        )
        conn.execute(
            "INSERT INTO Ingresos (OidIngreso, ConsecutivoIngreso, IdPaciente, ClaseIngreso, ViaIngreso, "
            "TipoRiesgo, FechaIngreso, FechaHospitalizacion, OidTriageA, CodigoCama, NombreCama, "
            "NombreGrupoCama, NombreSubgrupoCama, CodigoDiagnostico, NombreDiagnostico) "
            "VALUES (?, ?, ?, ?, 'Urgencias', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (admission_id, str(admission_id), patient_id,
             "Hospitalario" if bed else "Ambulatorio", MISSING, now, now if bed else None, triage_id,
             bed["CodigoCama"] if bed else MISSING, bed["NombreCama"] if bed else MISSING,
             bed["GrupoCama"] if bed else MISSING, bed["SubgrupoCama"] if bed else MISSING,
             MISSING, (data.diagnosis or "").strip() or MISSING),
        )
        _upsert_management(conn, admission_id, {
            "Origen": "App",
            "DocumentoHash": hash_document(data.dni),
            "Estado": data.status or None,
            "Departamento": data.department or None,
            "TipoSangre": data.blood_type,
            "Alergias": data.allergies,
            "SaturacionO2": vitals.spo2,
            "Notas": data.notes,
            "MedicoAsignadoId": data.doctor_assigned_id,
            "MedicoAsignadoNombre": data.doctor_assigned_name or data.doctor_name,
        })
        conn.commit()
    except sqlite3.DatabaseError:
        conn.rollback()
        raise
    return get_patient(conn, f"{ID_PREFIX}{admission_id}")


def update_patient(conn: sqlite3.Connection, patient_id: str, data: PatientUpdate) -> Patient:
    """Actualización parcial o completa (el frontend reenvía el objeto entero) en una transacción."""
    oid = parse_patient_id(patient_id)
    current = _get_row(conn, oid)
    fields = data.model_dump(exclude_unset=True)
    management: dict[str, Any] = {}

    try:
        # Paciente (el nombre nunca se guarda: se conserva el seudónimo)
        if data.gender:
            conn.execute("UPDATE Paciente SET Sexo = ? WHERE IdPaciente = ?",
                         (data.gender, current["IdPaciente"]))
        if data.age is not None and data.age != current["Edad"]:
            conn.execute("UPDATE Paciente SET FechaNacimiento = ? WHERE IdPaciente = ?",
                         (_birth_date_for_age(data.age), current["IdPaciente"]))

        # Ingreso
        if data.diagnosis and data.diagnosis != current["NombreDiagnostico"]:
            conn.execute("UPDATE Ingresos SET NombreDiagnostico = ? WHERE OidIngreso = ?",
                         (data.diagnosis.strip(), oid))
        discharging = data.status == DISCHARGED
        if data.bed_id and data.bed_id != current["CodigoCama"] and not discharging:
            bed = _get_available_bed(conn, data.bed_id, current_oid=oid)
            conn.execute(
                "UPDATE Ingresos SET CodigoCama = ?, NombreCama = ?, NombreGrupoCama = ?, "
                "NombreSubgrupoCama = ?, FechaHospitalizacion = COALESCE(FechaHospitalizacion, ?) "
                "WHERE OidIngreso = ?",
                (bed["CodigoCama"], bed["NombreCama"], bed["GrupoCama"], bed["SubgrupoCama"],
                 now_str(), oid),
            )

        # Triage y signos vitales
        if data.vitals or data.triage_level:
            _update_triage(conn, oid, current, data)

        # Campos de gestión (solo los enviados)
        for field, column in _MANAGEMENT_FIELDS.items():
            if field in fields:
                management[column] = fields[field]
        if data.vitals and data.vitals.spo2:
            management["SaturacionO2"] = data.vitals.spo2
        # Solo se fija un estado/servicio manual si cambia respecto al derivado,
        # para que reenviar el objeto completo no "congele" el estado automático.
        if data.status and data.status != current["Estado"]:
            management["Estado"] = data.status
            if discharging:
                management["FechaAlta"] = data.discharge_date or now_str()
            elif current["Estado"] == DISCHARGED:
                management["FechaAlta"] = None
        if data.department and data.department != current["Servicio"]:
            management["Departamento"] = data.department
        if management:
            _upsert_management(conn, oid, management)
        conn.commit()
    except sqlite3.DatabaseError:
        conn.rollback()
        raise
    return get_patient(conn, patient_id)


def _update_triage(
    conn: sqlite3.Connection, oid: int, current: sqlite3.Row, data: PatientUpdate
) -> None:
    """Actualiza signos vitales y nivel de triage; crea el triage si el ingreso no tenía."""
    triage_id = conn.execute(
        "SELECT OidTriageA FROM Ingresos WHERE OidIngreso = ?", (oid,)
    ).fetchone()[0]
    vitals = data.vitals or Vitals()
    if not triage_id:
        triage_id = _next_id(conn, "Triage", "OidTriage")
        level = data.triage_level or current["NivelTriage"] or DEFAULT_TRIAGE_LEVEL
        conn.execute(
            "INSERT INTO Triage (OidTriage, FechaTriage, MotivoConsulta, TensionArterial, "
            "FrecuenciaCardiaca, FrecuenciaRespiratoria, Temperatura, IdPaciente2, CodigoTriage, "
            "ClasificacionTriage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (triage_id, now_str(), MISSING, vitals.bp or MISSING, _extract_number(vitals.hr), MISSING,
             _extract_number(vitals.temp), current["IdPaciente"], str(level),
             f"REGISTRO APP - TRIAGE {level}"),
        )
        conn.execute("UPDATE Ingresos SET OidTriageA = ? WHERE OidIngreso = ?", (triage_id, oid))
        return

    if data.vitals:
        updates = {
            "TensionArterial": vitals.bp,
            "FrecuenciaCardiaca": _extract_number(vitals.hr) if vitals.hr else None,
            "Temperatura": _extract_number(vitals.temp) if vitals.temp else None,
        }
        for column, value in updates.items():
            if value and value != MISSING:
                conn.execute(f"UPDATE Triage SET {column} = ? WHERE OidTriage = ?", (value, triage_id))
    if data.triage_level and data.triage_level != current["NivelTriage"]:
        conn.execute(
            "UPDATE Triage SET ClasificacionTriage = ?, CodigoTriage = ? WHERE OidTriage = ?",
            (f"RECLASIFICADO APP - TRIAGE {data.triage_level}", str(data.triage_level), triage_id),
        )


def delete_patient(conn: sqlite3.Connection, patient_id: str) -> None:
    """Borrado lógico: el registro del HIS se conserva, pero deja de verse en la app."""
    oid = parse_patient_id(patient_id)
    _get_row(conn, oid)
    _upsert_management(conn, oid, {"Eliminado": 1})
    conn.commit()
