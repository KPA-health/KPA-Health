"""Traducción de errores a códigos HTTP y compatibilidad del contrato del agente IA."""
import io
import sqlite3

from backend.services.ai_agent.guardrails import messages
from backend.services.ai_agent.nl2sql_agent import parse_llm_output


def _raise(exc):
    def failing(*_args, **_kwargs):
        raise exc
    return failing


def test_locked_database_returns_503(client, monkeypatch):
    monkeypatch.setattr("backend.models.stats_model.get_stats",
                        _raise(sqlite3.OperationalError("database is locked")))
    response = client.get("/api/stats")
    assert response.status_code == 503
    assert response.json() == {"success": False,
                               "message": "La base de datos está ocupada. Intente de nuevo en unos segundos."}


def test_database_error_returns_500_without_leaking_details(client, monkeypatch):
    monkeypatch.setattr("backend.models.stats_model.get_stats",
                        _raise(sqlite3.DatabaseError("no such column: Secreto")))
    response = client.get("/api/stats")
    assert response.status_code == 500
    assert "Secreto" not in response.text and response.json()["success"] is False


def test_unexpected_error_returns_500(client, monkeypatch):
    # `client` garantiza que el entorno ya apunta a la BD temporal de pruebas
    from fastapi.testclient import TestClient
    from backend.main import create_app

    monkeypatch.setattr("backend.models.stats_model.get_stats", _raise(RuntimeError("fallo interno")))
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/stats")
    assert response.status_code == 500
    assert response.json()["message"] == "Error interno del servidor" and "fallo" not in response.text


def test_request_schema_errors_are_422_and_business_errors_400(client):
    assert client.post("/api/patients", json={"dni": "123"}).status_code == 422          # falta `name`
    assert client.get("/api/dashboard", params={"period": "siglo"}).status_code == 400   # regla de negocio


def test_upload_accepts_english_alias(client):
    content = "OidIngreso|FechaAtencion\n999000077|2026-09-21 10:00:00\n"
    response = client.post("/api/upload/care",
                           files={"file": ("Atencion.txt", io.BytesIO(content.encode()), "text/plain")})
    assert response.status_code == 200 and response.json()["data"]["table"] == "Atencion"


def test_legacy_spanish_categories_from_the_model_are_normalized():
    output = parse_llm_output('{"categoria": "fuera_de_alcance", "sql": null, "explanation": "x"}')
    assert output.category == messages.CATEGORY_OUT_OF_SCOPE and output.sql is None
    assert parse_llm_output('{"category": "desconocida", "sql": "SELECT 1"}').category == messages.CATEGORY_HOSPITAL
