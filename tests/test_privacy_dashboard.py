"""Privacidad de datos personales y contrato del dashboard BI."""
import json
import sqlite3

from backend.core.config import get_settings
from backend.core.privacy import hash_document

REAL_NAME = "Valeria Patricia Rivas Soto"
REAL_DOCUMENT = "1061987654"


def _db():
    return sqlite3.connect(get_settings().database_path)


def _free_bed(client) -> str:
    wings = client.get("/api/rooms").json()["data"]
    return next(b["id"] for w in wings for b in w["beds"] if b["status"] == "Libre")


def test_admission_never_stores_or_returns_personal_data(client):
    bed = _free_bed(client)
    response = client.post("/api/patients", json={
        "name": REAL_NAME, "dni": REAL_DOCUMENT, "age": 34, "gender": "Femenino", "phone": "3001234567",
        "triageLevel": 2, "bedId": bed, "diagnosis": "Neumonía adquirida en la comunidad",
    })
    assert response.status_code == 201, response.text
    body_text = response.text
    patient = response.json()["data"]
    assert REAL_NAME not in body_text and REAL_DOCUMENT not in body_text and "3001234567" not in body_text
    assert patient["name"].startswith("Paciente_") and "•••" in patient["dni"]

    oid = int(patient["id"].removeprefix("ING-"))
    with _db() as conn:
        name = conn.execute(
            "SELECT p.NombrePaciente FROM Ingresos i JOIN Paciente p ON p.IdPaciente = i.IdPaciente "
            "WHERE i.OidIngreso = ?", (oid,)).fetchone()[0]
        doc_clear, doc_hash, phone = conn.execute(
            "SELECT DocumentoIdentidad, DocumentoHash, Telefono FROM IngresoGestion WHERE OidIngreso = ?",
            (oid,)).fetchone()
    assert name.startswith("Paciente_") and REAL_NAME not in name
    assert doc_clear is None and phone is None and doc_hash == hash_document(REAL_DOCUMENT)

    # Se puede buscar por documento (comparando hashes) sin que el documento esté guardado
    found = client.get("/api/patients", params={"q": REAL_DOCUMENT}).json()
    assert found["count"] == 1 and found["data"][0]["id"] == patient["id"]

    # Los dashboards reflejan el ingreso de inmediato y tampoco exponen datos personales
    dashboard = client.get("/api/dashboard", params={"period": "today"})
    assert REAL_NAME not in dashboard.text and REAL_DOCUMENT not in dashboard.text
    client.put(f"/api/patients/{patient['id']}", json={"status": "Dado de Alta"})


def test_bed_status_and_appointments_do_not_keep_names(client):
    bed = _free_bed(client)
    client.put("/api/rooms/bed-status", json={"bedId": bed, "status": "Ocupada",
                                              "patientId": "ING-1", "patientName": REAL_NAME})
    assert REAL_NAME not in client.get("/api/rooms").text
    client.put("/api/rooms/bed-status", json={"bedId": bed, "status": "Auto"})

    created = client.post("/api/appointments", json={
        "patientId": "PAC-900", "patientName": REAL_NAME, "doctorName": "Dr. Demo", "date": "2026-09-25",
    }).json()["data"]
    assert created["patientName"] == "Paciente PAC-900"
    with _db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM Cita WHERE NombrePaciente = ?", (REAL_NAME,)).fetchone()[0] == 0


def test_dashboard_contract_and_filters(client):
    data = client.get("/api/dashboard", params={"period": "7d"}).json()["data"]
    for key in ("kpis", "occupancyTrend", "serviceDistribution", "wards", "urgentPatients", "criticalMeds",
                "services", "referenceDate"):
        assert key in data
    kpis = data["kpis"]
    assert kpis["totalBeds"] == kpis["occupiedBeds"] + kpis["freeBeds"] + sum(w["unavailable"] for w in data["wards"])
    assert len(data["occupancyTrend"]["labels"]) == 7
    assert all(p["name"].startswith("Paciente") for p in data["urgentPatients"])

    service = data["services"][0]
    filtered = client.get("/api/dashboard", params={"period": "30d", "service": service}).json()["data"]
    assert filtered["service"] == service and filtered["kpis"]["totalBeds"] <= kpis["totalBeds"]
    assert client.get("/api/dashboard", params={"period": "siglo"}).status_code == 422
    assert client.get("/api/dashboard", params={"service": "Marte"}).status_code == 422


def test_health_reports_all_tables(client):
    counts = client.get("/api/health").json()["rowCounts"]
    assert set(counts) == {"Paciente", "Triage", "Ingresos", "Atencion", "MedicamentoInsumo",
                           "Servicios", "ProgramacionCirugia"}


def test_no_personal_data_in_patient_listing(client):
    body = client.get("/api/patients", params={"limit": 50}).json()
    assert all(p["name"].startswith("Paciente") and "•••" in p["dni"] for p in body["data"])
    assert all(p["phone"] is None for p in body["data"])
    json.dumps(body)  # serializable
