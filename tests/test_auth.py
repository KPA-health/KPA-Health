"""Login JWT y control de acceso por roles (admin: todo · user: dashboard, asistente, ingresos)."""
import time

import jwt
import pytest

from backend.auth.passwords import hash_password, verify_password
from backend.auth.service import reset_attempts
from backend.core.config import get_settings

ADMIN = ("admin", "Admin2026*")
USER = ("usuario", "Usuario2026*")


@pytest.fixture
def auth_on(client, monkeypatch):
    """Activa la autenticación solo durante la prueba."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    reset_attempts()
    yield client
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    reset_attempts()


def _token(client, credentials) -> dict:
    response = client.post("/api/auth/login", json={"username": credentials[0], "password": credentials[1]})
    assert response.status_code == 200, response.text
    return response.json()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_password_hashing():
    stored = hash_password("ClaveSegura1", iterations=1000)
    assert stored.startswith("pbkdf2_sha256$") and "ClaveSegura1" not in stored
    assert verify_password("ClaveSegura1", stored) and not verify_password("otra", stored)


def test_login_returns_jwt_with_role_and_permissions(auth_on):
    body = _token(auth_on, ADMIN)
    assert body["tokenType"] == "bearer" and body["expiresIn"] > 0
    assert body["user"]["role"] == "admin" and "data" in body["user"]["permissions"]
    claims = jwt.decode(body["accessToken"], get_settings().auth.jwt_secret, algorithms=["HS256"],
                        issuer="kpa-health-hslv")
    assert claims["sub"] == "admin" and claims["role"] == "admin"

    user = _token(auth_on, USER)["user"]
    assert user["role"] == "user" and sorted(user["permissions"]) == ["admissions", "assistant", "dashboard"]


def test_invalid_credentials_and_missing_token(auth_on):
    bad = auth_on.post("/api/auth/login", json={"username": "admin", "password": "incorrecta"})
    assert bad.status_code == 401 and bad.json()["message"] == "Usuario o contraseña incorrectos"
    unknown = auth_on.post("/api/auth/login", json={"username": "fantasma", "password": "x"})
    assert unknown.json()["message"] == bad.json()["message"]  # no revela qué usuarios existen
    assert auth_on.get("/api/dashboard").status_code == 401
    assert auth_on.get("/api/dashboard", headers=_h("token.falso.123")).status_code == 401


def test_expired_token_is_rejected(auth_on):
    settings = get_settings().auth
    expired = jwt.encode({"sub": "admin", "role": "admin", "iss": "kpa-health-hslv",
                          "iat": int(time.time()) - 7200, "exp": int(time.time()) - 60},
                         settings.jwt_secret, algorithm="HS256")
    response = auth_on.get("/api/auth/me", headers=_h(expired))
    assert response.status_code == 401 and "expiró" in response.json()["message"]


def test_user_role_access(auth_on):
    headers = _h(_token(auth_on, USER)["accessToken"])
    # Permitido: dashboard, asistente, gestión de ingresos
    assert auth_on.get("/api/dashboard", headers=headers).status_code == 200
    assert auth_on.get("/api/ai/providers", headers=headers).status_code == 200
    assert auth_on.get("/api/rooms", headers=headers).status_code == 200
    assert auth_on.get("/api/patients", params={"limit": 1}, headers=headers).status_code == 200
    # Prohibido: gestión de datos, usuarios y acciones de administración
    upload = auth_on.post("/api/upload/atencion", headers=headers,
                          files={"file": ("a.txt", b"OidIngreso|FechaAtencion\n", "text/plain")})
    assert upload.status_code == 403 and "permisos" in upload.json()["message"]
    assert auth_on.get("/api/auth/users", headers=headers).status_code == 403
    assert auth_on.put("/api/rooms/bed-status", json={"bedId": "X", "status": "Libre"}, headers=headers).status_code == 403
    assert auth_on.delete("/api/patients/ING-1", headers=headers).status_code == 403


def test_admin_has_full_access_and_manages_users(auth_on):
    headers = _h(_token(auth_on, ADMIN)["accessToken"])
    assert auth_on.get("/api/upload/types", headers=headers).status_code == 200
    created = auth_on.post("/api/auth/users", headers=headers,
                           json={"username": "enfermera1", "password": "Enfermera2026*", "role": "user", "name": "Enfermería"})
    assert created.status_code == 201 and created.json()["data"]["role"] == "user"
    assert auth_on.post("/api/auth/users", headers=headers,
                        json={"username": "enfermera1", "password": "Enfermera2026*"}).status_code == 409
    users = auth_on.get("/api/auth/users", headers=headers).json()
    assert {"admin", "usuario", "enfermera1"} <= {u["username"] for u in users["data"]}

    # Desactivar un usuario invalida sus tokens vigentes
    token = _token(auth_on, ("enfermera1", "Enfermera2026*"))["accessToken"]
    auth_on.patch("/api/auth/users/enfermera1", headers=headers, json={"active": False})
    assert auth_on.get("/api/auth/me", headers=_h(token)).status_code == 401
    # Un admin no puede quitarse su propio rol
    assert auth_on.patch("/api/auth/users/admin", headers=headers, json={"role": "user"}).status_code == 403


def test_lockout_after_failed_attempts(auth_on):
    for _ in range(get_settings().auth.max_failed_attempts):
        auth_on.post("/api/auth/login", json={"username": "usuario", "password": "mala"})
    locked = auth_on.post("/api/auth/login", json={"username": "usuario", "password": "Usuario2026*"})
    assert locked.status_code == 429 and "Demasiados intentos" in locked.json()["message"]


def test_public_endpoints(auth_on):
    config = auth_on.get("/api/auth/config").json()
    assert config["authEnabled"] is True and "users" in config["roles"]["admin"]["permissions"]
    assert auth_on.get("/api/health").status_code == 200
