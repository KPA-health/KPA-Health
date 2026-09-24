"""Regresiones de seguridad en los bordes HTTP y en la entrada de datos."""
import io
import sqlite3

from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.core.security import _InlineInventory, _hash
from backend.main import create_app
from backend.schemas.auth import LoginRequest
from backend.schemas.patients import PatientCreate
from backend.services.ai_agent import sql_executor


def test_cookie_session_requires_csrf_and_sets_security_headers(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(), base_url="https://testserver") as browser:
            login = browser.post("/api/auth/login", json={"username": "admin", "password": "Admin2026*"})
            assert login.status_code == 200
            cookies = login.headers.get_list("set-cookie")
            assert any("medipulse_session=" in c and "httponly" in c.lower()
                       and "secure" in c.lower() and "samesite=strict" in c.lower() for c in cookies)
            assert any("medipulse_csrf=" in c and "secure" in c.lower() for c in cookies)
            csp = login.headers["content-security-policy"]
            assert "object-src 'none'" in csp and "script-src" in csp
            assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
            assert "'unsafe-inline'" not in csp.split("style-src", 1)[1].split(";", 1)[0]
            assert browser.get("/api/auth/me").status_code == 200
            assert browser.post("/api/auth/logout").status_code == 403
            token = browser.cookies.get("medipulse_csrf")
            assert browser.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
            assert browser.get("/api/auth/me").status_code == 401
    finally:
        monkeypatch.setenv("AUTH_ENABLED", "false")
        get_settings.cache_clear()


def test_upload_rejects_traversal_and_false_mime(client):
    for name in ("../paciente.txt", "..\\paciente.txt", "%2e%2e%2fpaciente.txt"):
        response = client.post("/api/upload/paciente",
                               files={"file": (name, io.BytesIO(b"A|B\n1|2\n"), "text/plain")})
        assert response.status_code == 400, name
    response = client.post("/api/upload/paciente",
                           files={"file": ("paciente.txt", io.BytesIO(b"A|B\n1|2\n"), "application/octet-stream")})
    assert response.status_code == 400


def test_form_validation_rejects_markup_and_sql_commands():
    from pydantic import ValidationError
    for payload in ({"username": "<script>", "password": "x"},
                    {"username": "admin' OR 1=1", "password": "x"}):
        try:
            LoginRequest.model_validate(payload)
        except ValidationError:
            pass
        else:
            raise AssertionError("Se aceptó un usuario inseguro")
    for name in ("<script>alert(1)</script>", "Ana'; DROP TABLE Paciente"):
        try:
            PatientCreate.model_validate({"name": name, "dni": "12345"})
        except ValidationError:
            pass
        else:
            raise AssertionError("Se aceptó un nombre inseguro")


def test_generated_sql_values_are_bound_in_correct_positions(monkeypatch):
    monkeypatch.setattr(sql_executor, "connect_readonly", lambda **_: sqlite3.connect(":memory:"))
    result = sql_executor.execute_readonly(
        "SELECT 'primero' AS valor WHERE 'izquierda' = 'izquierda' AND 'derecha' = 'derecha' LIMIT 1", 2
    )
    assert result.rows == [["primero"]]


def test_api_documentation_inline_bootstrap_has_exact_csp_hash(client):
    for path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
        response = client.get(path)
        assert response.status_code == 200
        inventory = _InlineInventory()
        inventory.feed(response.text)
        policy = response.headers["content-security-policy"]
        assert all(_hash(block) in policy for block in inventory.scripts | inventory.styles)


def test_frontend_has_no_inline_script_or_event_handlers(client):
    response = client.get("/")
    assert response.status_code == 200
    inventory = _InlineInventory()
    inventory.feed(response.text)
    assert not inventory.scripts and not inventory.handlers and not inventory.styles
    assert "script-src 'self'" in response.headers["content-security-policy"]
