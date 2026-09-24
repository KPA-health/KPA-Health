"""
Repositorio de camas (/rooms).

El estado de cada cama sale de la vista EstadoCamas (ocupación estimada a la
fecha de referencia). Un usuario puede forzar un estado (Desinfección,
Mantenimiento, etc.) que se guarda en CamaEstadoManual.
"""
from __future__ import annotations

import sqlite3
from itertools import groupby

from backend.core.errors import NotFoundError, ValidationError
from backend.core.privacy import patient_pseudonym
from backend.core.timeutils import now_str, to_minutes_precision
from backend.schemas.resources import Bed, BedStatusUpdate, Wing

BED_STATUSES = {"Ocupada", "Libre", "Desinfección", "Mantenimiento"}
AUTO_STATUS = {None, "", "Auto", "auto"}

_ROOMS_SQL = """
SELECT e.*, cm.IdPacienteApp
FROM EstadoCamas e
LEFT JOIN CamaEstadoManual cm ON cm.CodigoCama = e.CodigoCama
ORDER BY e.Servicio, e.SubgrupoCama, e.CodigoCama
"""


def _to_bed(row: sqlite3.Row) -> Bed:
    occupied = row["Estado"] == "Ocupada"
    patient_id = row["IdPacienteApp"] or (f"ING-{row['OidIngreso']}" if row["OidIngreso"] else None)
    # Privacidad: solo seudónimos, nunca el nombre del paciente
    if row["IdPaciente"]:
        patient_name = patient_pseudonym(row["IdPaciente"])
    else:
        patient_name = f"Paciente {row['IdPacienteApp']}" if row["IdPacienteApp"] else "Paciente anónimo"
    return Bed(
        id=row["CodigoCama"],
        code=f"Cama {row['CodigoCama']}",
        status=row["Estado"],
        patient_id=patient_id if occupied else None,
        patient_name=patient_name if occupied else None,
        type=row["Servicio"],
        occupied_since=to_minutes_precision(row["OcupadaDesde"]) if occupied else None,
    )


def list_rooms(conn: sqlite3.Connection) -> list[Wing]:
    rows = conn.execute(_ROOMS_SQL).fetchall()
    wings = []
    for (service, subgroup), group in groupby(rows, key=lambda r: (r["Servicio"], r["SubgrupoCama"])):
        group = list(group)
        wings.append(Wing(
            wing=subgroup or service,
            floor=service,
            code=group[0]["GrupoCama"],
            beds=[_to_bed(r) for r in group],
        ))
    return wings


def update_bed_status(conn: sqlite3.Connection, data: BedStatusUpdate) -> None:
    exists = conn.execute(
        "SELECT 1 FROM CatalogoCamas WHERE CodigoCama = ?", (data.bed_id,)
    ).fetchone()
    if not exists:
        raise NotFoundError(f"La cama {data.bed_id} no existe en el catálogo de camas")

    if data.status in AUTO_STATUS:
        # Sin estado manual: vuelve a la ocupación calculada desde el HIS
        conn.execute("DELETE FROM CamaEstadoManual WHERE CodigoCama = ?", (data.bed_id,))
    else:
        if data.status not in BED_STATUSES:
            raise ValidationError(
                f"Estado de cama inválido: {data.status}", {"allowed": sorted(BED_STATUSES)}
            )
        keep_patient = data.status == "Ocupada"
        conn.execute(
            "INSERT INTO CamaEstadoManual (CodigoCama, Estado, IdPacienteApp, NombrePacienteApp, "
            "ActualizadoEn) VALUES (?, ?, ?, ?, ?) ON CONFLICT(CodigoCama) DO UPDATE SET "
            "Estado = excluded.Estado, IdPacienteApp = excluded.IdPacienteApp, "
            "NombrePacienteApp = excluded.NombrePacienteApp, ActualizadoEn = excluded.ActualizadoEn",
            # patient_name se ignora a propósito: nunca se almacenan nombres
            (data.bed_id, data.status, data.patient_id if keep_patient else None, None, now_str()),
        )
    conn.commit()
