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

from backend.auth import repository
from backend.auth.passwords import verify_password
from backend.auth.permissions import ROLE_LABELS, permissions_for
from backend.auth.tokens import create_access_token
from backend.core.config import get_settings
from backend.core.errors import AppError

INVALID_CREDENTIALS = "Usuario o contraseña incorrectos"


class AuthenticationError(AppError):
    status_code = 401


class TooManyAttemptsError(AppError):
    status_code = 429


@dataclass
class _Attempts:
    failures: int = 0
    locked_until: float = 0.0


_attempts: dict[str, _Attempts] = {}
_lock = threading.Lock()


def _key(username: str) -> str:
    return username.strip().lower()


def reset_attempts() -> None:
    with _lock:
        _attempts.clear()


def user_payload(row: sqlite3.Row) -> dict:
    return {
        "username": row["Username"],
        "name": row["NombreVisible"],
        "role": row["Rol"],
        "roleLabel": ROLE_LABELS.get(row["Rol"], row["Rol"]),
        "permissions": permissions_for(row["Rol"]),
    }


def login(conn: sqlite3.Connection, username: str, password: str) -> dict:
    auth = get_settings().auth
    key = _key(username)
    now = time.monotonic()
    with _lock:
        state = _attempts.setdefault(key, _Attempts())
        if state.locked_until > now:
            wait = int(state.locked_until - now) + 1
            raise TooManyAttemptsError(f"Demasiados intentos fallidos. Intente de nuevo en {wait} segundos.")

    user = repository.get_user(conn, username.strip())
    valid = bool(user) and bool(user["Activo"]) and verify_password(password, user["PasswordHash"])
    if not valid:
        with _lock:
            state.failures += 1
            if state.failures >= auth.max_failed_attempts:
                state.failures = 0
                state.locked_until = now + auth.lockout_seconds
        raise AuthenticationError(INVALID_CREDENTIALS)

    with _lock:
        _attempts.pop(key, None)
    repository.touch_last_login(conn, user["IdUsuario"])
    token, expires_in = create_access_token(user["Username"], user["Rol"], user["NombreVisible"])
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in, "user": user_payload(user)}
