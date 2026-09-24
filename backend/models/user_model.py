"""
Modelo de usuarios (capa Modelo): tabla Usuario y usuarios iniciales definidos en .env.

Las contraseñas nunca se guardan en claro: solo el hash PBKDF2 (ver password_hasher.py).
"""
from __future__ import annotations

import logging
import sqlite3

from backend.core.config import get_settings
from backend.core.errors import BadRequestError, ConflictError, NotFoundError
from backend.core.time_utils import now_str
from backend.services.auth.password_hasher import hash_password
from backend.services.auth.permissions import ROLE_ADMIN, ROLE_PERMISSIONS, ROLE_USER

logger = logging.getLogger("medipulse.auth")

MIN_PASSWORD_LENGTH = 8

USERS_DDL = """
CREATE TABLE IF NOT EXISTS Usuario (
    IdUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    NombreVisible TEXT NOT NULL,
    Rol TEXT NOT NULL CHECK (Rol IN ('admin', 'user')),
    PasswordHash TEXT NOT NULL,
    Activo INTEGER NOT NULL DEFAULT 1,
    CreadoEn TEXT,
    UltimoAcceso TEXT
);
"""


def ensure_users(conn: sqlite3.Connection) -> None:
    """Crea la tabla y los usuarios iniciales si no existen (idempotente)."""
    conn.executescript(USERS_DDL)
    auth = get_settings().auth
    for username, password, role, name in (
        (auth.admin_username, auth.admin_password, ROLE_ADMIN, "Administrador del sistema"),
        (auth.user_username, auth.user_password, ROLE_USER, "Usuario clínico"),
    ):
        if not get_user(conn, username):
            create_user(conn, username, password, role, name)
            logger.info("Usuario inicial creado: %s (%s)", username, role)
    conn.commit()


def _validate_role(role: str) -> None:
    if role not in ROLE_PERMISSIONS:
        raise BadRequestError(f"Rol inválido: {role}", {"allowed": sorted(ROLE_PERMISSIONS)})


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise BadRequestError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")


def get_user(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    """Usuario por nombre (sin distinguir mayúsculas) o None."""
    return conn.execute("SELECT * FROM Usuario WHERE Username = ?", (username,)).fetchone()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todos los usuarios, agrupados por rol."""
    return conn.execute("SELECT * FROM Usuario ORDER BY Rol, Username").fetchall()


def create_user(conn: sqlite3.Connection, username: str, password: str, role: str, name: str) -> sqlite3.Row:
    """Crea un usuario activo; 409 si el nombre ya existe."""
    username = username.strip()
    _validate_role(role)
    _validate_password(password)
    if get_user(conn, username):
        raise ConflictError(f"El usuario '{username}' ya existe")
    conn.execute(
        "INSERT INTO Usuario (Username, NombreVisible, Rol, PasswordHash, Activo, CreadoEn) VALUES (?, ?, ?, ?, 1, ?)",
        (username, name.strip() or username, role, hash_password(password), now_str()),
    )
    conn.commit()
    return get_user(conn, username)


def update_user(conn: sqlite3.Connection, username: str, *, role: str | None = None,
                active: bool | None = None, password: str | None = None, name: str | None = None) -> sqlite3.Row:
    """Actualiza solo los campos recibidos (rol, estado, contraseña, nombre visible)."""
    user = get_user(conn, username)
    if user is None:
        raise NotFoundError(f"Usuario '{username}' no encontrado")
    if role is not None:
        _validate_role(role)
    if password is not None:
        _validate_password(password)
    updates = {}
    if role is not None:
        updates["Rol"] = role
    if active is not None:
        updates["Activo"] = 1 if active else 0
    if password is not None:
        updates["PasswordHash"] = hash_password(password)
    if name:
        updates["NombreVisible"] = name.strip()
    if updates:
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(f"UPDATE Usuario SET {assignments} WHERE IdUsuario = ?", (*updates.values(), user["IdUsuario"]))
        conn.commit()
    return get_user(conn, username)


def touch_last_login(conn: sqlite3.Connection, user_id: int) -> None:
    """Registra la fecha del último inicio de sesión exitoso."""
    conn.execute("UPDATE Usuario SET UltimoAcceso = ? WHERE IdUsuario = ?", (now_str(), user_id))
    conn.commit()
