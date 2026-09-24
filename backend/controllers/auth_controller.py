"""Controlador de autenticación (login JWT) y administración de usuarios: /auth/*."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.controllers.dependencies import CurrentUser, get_current_user, require_admin
from backend.core.config import get_settings
from backend.core.errors import ForbiddenError
from backend.models import user_model
from backend.models.db_connection import get_db
from backend.schemas.auth import LoginRequest, LoginResponse, UserCreate, UserOut, UserUpdate
from backend.schemas.common import ItemResponse, ListResponse
from backend.services.auth import auth_service
from backend.services.auth.permissions import ROLE_LABELS, ROLE_PERMISSIONS, ROLE_USER, permissions_for

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _to_user_out(row: sqlite3.Row) -> UserOut:
    """Fila de Usuario -> DTO público (sin hash de contraseña)."""
    return UserOut(
        username=row["Username"], name=row["NombreVisible"], role=row["Rol"],
        role_label=ROLE_LABELS.get(row["Rol"], row["Rol"]), permissions=permissions_for(row["Rol"]),
        active=bool(row["Activo"]), last_login=row["UltimoAcceso"],
    )


@router.get("/config")
def get_auth_config():
    """Público: indica a la SPA si debe pedir login y qué permisos tiene cada rol."""
    return {
        "authEnabled": get_settings().auth.enabled,
        "roles": {role: {"label": ROLE_LABELS[role], "permissions": sorted(permissions)}
                  for role, permissions in ROLE_PERMISSIONS.items()},
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Emite un JWT. 401 con credenciales inválidas; 429 tras varios intentos fallidos."""
    return auth_service.login(conn, payload.username, payload.password)


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser = Depends(get_current_user)):
    """Usuario de la sesión actual (la SPA lo usa para restaurar la sesión al recargar)."""
    return UserOut(username=user.username, name=user.name, role=user.role,
                   role_label=ROLE_LABELS.get(user.role, user.role), permissions=user.permissions)


@router.get("/users", response_model=ListResponse[UserOut], dependencies=[Depends(require_admin)])
def list_users(conn: sqlite3.Connection = Depends(get_db)):
    users = [_to_user_out(row) for row in user_model.list_users(conn)]
    return ListResponse[UserOut](data=users, count=len(users))


@router.post("/users", response_model=ItemResponse[UserOut], status_code=201, dependencies=[Depends(require_admin)])
def create_user(payload: UserCreate, conn: sqlite3.Connection = Depends(get_db)):
    row = user_model.create_user(conn, payload.username, payload.password, payload.role, payload.name)
    return ItemResponse[UserOut](data=_to_user_out(row), message="Usuario creado")


@router.patch("/users/{username}", response_model=ItemResponse[UserOut])
def update_user(username: str, payload: UserUpdate, conn: sqlite3.Connection = Depends(get_db),
                admin: CurrentUser = Depends(require_admin)):
    """Un administrador no puede quitarse a sí mismo el rol ni desactivarse (evita quedar sin admins)."""
    is_self = username.lower() == admin.username.lower()
    if is_self and (payload.role == ROLE_USER or payload.active is False):
        raise ForbiddenError("No puede quitarse su propio rol de administrador ni desactivarse")
    row = user_model.update_user(conn, username, role=payload.role, active=payload.active,
                                 password=payload.password, name=payload.name)
    return ItemResponse[UserOut](data=_to_user_out(row), message="Usuario actualizado")
