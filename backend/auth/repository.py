"""Tabla Usuario y usuarios iniciales (admin y user) configurados en .env."""
from __future__ import annotations

import logging
import sqlite3

from backend.auth.passwords import hash_password
from backend.auth.permissions import ROLE_ADMIN, ROLE_PERMISSIONS, ROLE_USER
from backend.core.config import get_settings
from backend.core.errors import ConflictError, NotFoundError, ValidationError
from backend.core.timeutils import now_str

logger = logging.getLogger("medipulse.auth")

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


def get_user(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM Usuario WHERE Username = ?", (username,)).fetchone()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM Usuario ORDER BY Rol, Username").fetchall()


def create_user(conn: sqlite3.Connection, username: str, password: str, role: str, name: str) -> sqlite3.Row:
    username = username.strip()
    if role not in ROLE_PERMISSIONS:
        raise ValidationError(f"Rol inválido: {role}", {"allowed": sorted(ROLE_PERMISSIONS)})
    if len(password) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres")
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
    user = get_user(conn, username)
    if user is None:
        raise NotFoundError(f"Usuario '{username}' no encontrado")
    if role is not None and role not in ROLE_PERMISSIONS:
        raise ValidationError(f"Rol inválido: {role}", {"allowed": sorted(ROLE_PERMISSIONS)})
    if password is not None and len(password) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres")
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
    conn.execute("UPDATE Usuario SET UltimoAcceso = ? WHERE IdUsuario = ?", (now_str(), user_id))
    conn.commit()
