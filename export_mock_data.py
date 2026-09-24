"""
Genera frontend/js/mockData.js con los últimos datos reales de hospital.db.

El modo respaldo del frontend (backend caído) deja de usar datos inventados:
usa una instantánea de la base de datos obtenida con los mismos controladores
de la API, así que los datos salen con la misma forma y la misma anonimización
(nombres seudonimizados, documentos enmascarados) que en /api.

Uso:  python export_mock_data.py            (tras setup_db.py o una carga nueva)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from backend.controllers import (  # noqa: E402  (tras cargar .env)
    appointment_controller, bed_controller, doctor_controller, patient_controller, pharmacy_controller,
)
from backend.models.db_connection import closing_connection  # noqa: E402

OUTPUT = Path(__file__).parent / "frontend" / "js" / "mockData.js"
MAX_PATIENTS = 60        # últimos ingresos (la API ya los ordena del más reciente al más antiguo)
MAX_PHARMACY = 80        # insumos más urgentes (la API ordena por criticidad)

TEMPLATE = """/**
 * MediPulse OS - Instantánea de respaldo de la base de datos (NO EDITAR A MANO)
 *
 * Generado por export_mock_data.py a partir de hospital.db el {generated}.
 * Se usa solo si el backend no responde. Contiene los últimos registros reales,
 * con la misma anonimización que la API. Para actualizarlo:  python export_mock_data.py
 */

window.MediPulse = window.MediPulse || {{}};

MediPulse.MockData = {{
  generatedAt: {generated_json},

  initialDoctors: {doctors},

  initialPatients: {patients},

  initialAppointments: {appointments},

  initialRooms: {rooms},

  initialPharmacy: {pharmacy},

  // Versión de la instantánea: si cambia, se regeneran los datos guardados en el navegador
  version: {version},

  // Inicializar almacenamiento con persistencia local
  initialize(force = false) {{
    if (localStorage.getItem('medipulse_mock_version') !== this.version) {{
      force = true;
      localStorage.setItem('medipulse_mock_version', this.version);
    }}
    const seeds = {{
      medipulse_patients: this.initialPatients,
      medipulse_doctors: this.initialDoctors,
      medipulse_appointments: this.initialAppointments,
      medipulse_rooms: this.initialRooms,
      medipulse_pharmacy: this.initialPharmacy
    }};
    Object.entries(seeds).forEach(([key, value]) => {{
      if (force || !localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(value));
    }});
  }}
}};
"""


def _data(response) -> list:
    return response.model_dump(by_alias=True, mode="json")["data"]


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ")


def main() -> None:
    with closing_connection() as conn:
        patients = _data(patient_controller.list_patients(None, None, None, None, MAX_PATIENTS, 0, conn))
        doctors = _data(doctor_controller.list_doctors(None, conn))
        appointments = _data(appointment_controller.list_appointments(None, None, None, conn))
        rooms = _data(bed_controller.list_rooms(conn))
        pharmacy = _data(pharmacy_controller.list_pharmacy_items(None, None, None, MAX_PHARMACY, conn))

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    OUTPUT.write_text(TEMPLATE.format(
        generated=generated, generated_json=json.dumps(generated),
        doctors=_js(doctors), patients=_js(patients), appointments=_js(appointments),
        rooms=_js(rooms), pharmacy=_js(pharmacy),
        version=json.dumps("db-" + datetime.now().strftime("%Y%m%d%H%M%S")),
    ), encoding="utf-8")
    beds = sum(len(wing["beds"]) for wing in rooms)
    print(f"{OUTPUT} generado: {len(patients)} pacientes, {len(doctors)} médicos, "
          f"{len(appointments)} citas, {beds} camas, {len(pharmacy)} insumos")


if __name__ == "__main__":
    main()
