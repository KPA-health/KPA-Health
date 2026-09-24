"""
Contrato REST: las respuestas deben tener exactamente la forma que consume
hospital-spa (apiClient.js / services / mockData.js).
"""
import io

PATIENT_KEYS = {
    "id", "dni", "name", "age", "gender", "bloodType", "admissionDate", "triageLevel", "status",
    "department", "roomNumber", "bedId", "doctorAssignedId", "doctorAssignedName", "diagnosis",
    "allergies", "vitals", "notes",
}
STATS_KEYS = {
    "activePatients", "criticalPatients", "totalBeds", "occupiedBeds", "freeBeds", "occupancyRate",
    "todayAppointments", "availableDoctors", "criticalMeds",
}


def _free_bed(client) -> str:
    wings = client.get("/api/rooms").json()["data"]
    return next(b["id"] for w in wings for b in w["beds"] if b["status"] == "Libre")


def _bed_status(client, bed_id: str) -> str:
    wings = client.get("/api/rooms").json()["data"]
    return next(b["status"] for w in wings for b in w["beds"] if b["id"] == bed_id)


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["rowCounts"]["Ingresos"] > 0


def test_stats_contract(client):
    data = client.get("/api/stats").json()["data"]
    assert STATS_KEYS <= data.keys()
    assert data["totalBeds"] == data["occupiedBeds"] + data["freeBeds"] + data["maintenanceBeds"]


def test_patients_list_and_filters(client):
    body = client.get("/api/patients", params={"limit": 5}).json()
    assert body["count"] > 0 and len(body["data"]) == 5
    assert PATIENT_KEYS <= body["data"][0].keys()
    assert {"bp", "hr", "temp", "spo2"} == body["data"][0]["vitals"].keys()
    triage = client.get("/api/patients", params={"triage": "1", "limit": 50}).json()["data"]
    assert all(p["triageLevel"] == 1 for p in triage)


def test_patient_lifecycle_updates_beds(client):
    bed = _free_bed(client)
    created = client.post("/api/patients", json={
        "name": "Paciente Demo", "dni": "1061000000", "age": 40, "gender": "Femenino",
        "triageLevel": 2, "department": "Urgencias", "bedId": bed, "diagnosis": "Dolor torácico",
        "vitals": {"bp": "130/85", "hr": "92 lpm", "temp": "37.2°C", "spo2": "96%"},
        "doctorName": "Dr. Alejandro Silva Torrico",
    })
    assert created.status_code == 201, created.text
    patient = created.json()["data"]
    assert patient["bedId"] == bed and patient["triageLevel"] == 2 and patient["vitals"]["hr"] == "92 lpm"
    assert _bed_status(client, bed) == "Ocupada"

    # La misma cama ya no se puede asignar
    conflict = client.post("/api/patients", json={"name": "Otro", "dni": "1", "bedId": bed})
    assert conflict.status_code == 409 and "message" in conflict.json()

    # Alta médica (flujo de patientService.discharge: PUT con el objeto completo)
    discharged = client.put(f"/api/patients/{patient['id']}", json={
        **patient, "status": "Dado de Alta", "bedId": None, "dischargeNotes": "Alta con control",
    })
    assert discharged.status_code == 200
    assert discharged.json()["data"]["status"] == "Dado de Alta"
    assert _bed_status(client, bed) == "Libre"

    assert client.delete(f"/api/patients/{patient['id']}").json()["success"] is True
    assert client.get(f"/api/patients/{patient['id']}").status_code == 404


def test_rooms_and_bed_status(client):
    bed = _free_bed(client)
    assert client.put("/api/rooms/bed-status", json={"bedId": bed, "status": "Desinfección"}).status_code == 200
    assert _bed_status(client, bed) == "Desinfección"
    client.put("/api/rooms/bed-status", json={"bedId": bed, "status": "Auto"})
    assert _bed_status(client, bed) == "Libre"
    assert client.put("/api/rooms/bed-status", json={"bedId": bed, "status": "Rota"}).status_code == 422


def test_pharmacy_update_recalculates_status(client):
    item = client.get("/api/pharmacy", params={"limit": 1}).json()["data"][0]
    updated = client.put(f"/api/pharmacy/{item['id']}", json={"stock": 0, "minStock": 10}).json()["data"]
    assert updated["status"] == "Crítico" and updated["simulatedStock"] is False
    updated = client.put(f"/api/pharmacy/{item['id']}", json={"stock": 100}).json()["data"]
    assert updated["status"] == "Adecuado"


def test_doctors_and_appointments(client):
    doctors = client.get("/api/doctors").json()
    assert doctors["count"] >= 1
    doctor = doctors["data"][0]
    assert client.put(f"/api/doctors/{doctor['id']}", json={"status": "En Consulta"}).json()["data"]["status"] == "En Consulta"

    created = client.post("/api/appointments", json={
        "patientName": "Paciente Demo", "doctorId": doctor["id"], "doctorName": doctor["name"],
        "specialty": doctor["specialty"], "date": "2026-09-24", "time": "08:00", "reason": "Control",
    })
    assert created.status_code == 201
    apt = created.json()["data"]
    assert apt["status"] == "Programada" and apt["priority"] == "Normal"
    assert client.patch(f"/api/appointments/{apt['id']}", json={"status": "Finalizada"}).json()["data"]["status"] == "Finalizada"
    listed = client.get("/api/appointments", params={"date": "2026-09-24", "doctorId": doctor["id"]}).json()["data"]
    assert any(a["id"] == apt["id"] for a in listed)
    assert client.delete(f"/api/appointments/{apt['id']}").json()["success"] is True


def test_v1_alias_matches_default_frontend_url(client):
    assert client.get("/v1/stats").status_code == 200


def test_upload_is_idempotent(client):
    content = "OidIngreso|FechaAtencion\n999000001|2026-09-21 10:00:00\n999000001|2026-09-21 11:00:00\n"
    first = client.post("/api/upload/atencion",
                        files={"file": ("Atencion.txt", io.BytesIO(content.encode()), "text/plain")})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["rowsInserted"] == 2
    second = client.post("/api/upload/atencion",
                         files={"file": ("Atencion.txt", io.BytesIO(content.encode()), "text/plain")})
    assert second.json()["data"]["rowsInserted"] == 0


def test_upload_applies_setup_db_cleaning(client):
    content = (
        "TipoDocumento|IdPaciente|NombrePaciente|FechaNacimiento|Sexo|Asegurador|Regimen|Departamento|Municipio|Zona\n"
        "CC|990000001|NOMBRE REAL| 1990-01-01|Femenino| EPS X ||CAUCA|POPAYÁN|Urbana\n"
    )
    response = client.post("/api/upload/paciente",
                           files={"file": ("Paciente.txt", io.BytesIO(content.encode()), "text/plain")})
    assert response.status_code == 200, response.text
    import sqlite3
    from backend.core.config import get_settings
    conn = sqlite3.connect(get_settings().database_path)
    row = conn.execute(
        "SELECT NombrePaciente, Asegurador, Regimen FROM Paciente WHERE IdPaciente = 990000001"
    ).fetchone()
    conn.close()
    assert row == ("Paciente_990000001", "EPS X", "No Registrado")


def test_upload_validation_errors(client):
    bad_columns = client.post("/api/upload/triage",
                              files={"file": ("Triage.txt", io.BytesIO(b"A|B\n1|2\n"), "text/plain")})
    assert bad_columns.status_code == 422 and "missingColumns" in bad_columns.json()["detail"]
    bad_type = client.post("/api/upload/camas",
                           files={"file": ("x.txt", io.BytesIO(b"A\n1\n"), "text/plain")})
    assert bad_type.status_code == 422
    bad_ext = client.post("/api/upload/paciente",
                          files={"file": ("x.xlsx", io.BytesIO(b"x"), "application/octet-stream")})
    assert bad_ext.status_code == 422
