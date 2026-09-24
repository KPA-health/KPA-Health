"""
Caso de uso de login.

Protección contra fuerza bruta: tras AUTH_MAX_FAILED_ATTEMPTS intentos fallidos
para un mismo usuario, se bloquea durante AUTH_LOCKOUT_SECONDS (en memoria).
El mensaje de error es el mismo si el usuario no existe o la contraseña es
incorrecta, para no revelar qué usuarios existen.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass

from backend.core.config import get_settings
from backend.core.errors import TooManyRequestsError, UnauthorizedError
from backend.models import user_model
from backend.services.auth.password_hasher import verify_password
from backend.services.auth.permissions import ROLE_LABELS, permissions_for
from backend.services.auth.token_service import create_access_token

INVALID_CREDENTIALS = "Usuario o contraseña incorrectos"


@dataclass
class _LoginAttempts:
    failures: int = 0
    locked_until: float = 0.0     # time.monotonic() hasta el que el usuario está bloqueado


# Estado en memoria por proceso: suficiente para un despliegue de un solo worker.
_attempts_by_user: dict[str, _LoginAttempts] = {}
_attempts_lock = threading.Lock()


def _attempts_key(username: str) -> str:
    return username.strip().lower()


def reset_attempts() -> None:
    """Olvida todos los intentos fallidos (lo usan las pruebas)."""
    with _attempts_lock:
        _attempts_by_user.clear()


def user_payload(row: sqlite3.Row) -> dict:
    """Datos públicos del usuario que la SPA guarda en la sesión (nunca el hash)."""
    return {
        "username": row["Username"],
        "name": row["NombreVisible"],
        "role": row["Rol"],
        "roleLabel": ROLE_LABELS.get(row["Rol"], row["Rol"]),
        "permissions": permissions_for(row["Rol"]),
    }


def login(conn: sqlite3.Connection, username: str, password: str) -> dict:
    """
    Valida credenciales y emite un JWT.

    Lanza 429 si el usuario está bloqueado y 401 si las credenciales no son válidas
    (mismo mensaje exista o no el usuario, para no revelar qué cuentas existen).
    """
    auth = get_settings().auth
    key = _attempts_key(username)
    now = time.monotonic()
    with _attempts_lock:
        state = _attempts_by_user.setdefault(key, _LoginAttempts())
        if state.locked_until > now:
            wait_seconds = int(state.locked_until - now) + 1
            raise TooManyRequestsError(
                f"Demasiados intentos fallidos. Intente de nuevo en {wait_seconds} segundos."
            )

    user = user_model.get_user(conn, username.strip())
    is_valid = bool(user) and bool(user["Activo"]) and verify_password(password, user["PasswordHash"])
    if not is_valid:
        with _attempts_lock:
            state.failures += 1
            if state.failures >= auth.max_failed_attempts:
                state.failures = 0
                state.locked_until = now + auth.lockout_seconds
        raise UnauthorizedError(INVALID_CREDENTIALS)

    with _attempts_lock:
        _attempts_by_user.pop(key, None)
    user_model.touch_last_login(conn, user["IdUsuario"])
    token, expires_in = create_access_token(user["Username"], user["Rol"], user["NombreVisible"])
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in, "user": user_payload(user)}
