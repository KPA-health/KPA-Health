"""Autenticación (login JWT) y administración de usuarios."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.auth import repository, service
from backend.auth.dependencies import CurrentUser, ForbiddenError, get_current_user, require_admin
from backend.auth.permissions import ROLE_LABELS, ROLE_PERMISSIONS, permissions_for
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.schemas.auth import LoginRequest, LoginResponse, UserCreate, UserOut, UserUpdate
from backend.schemas.common import ItemResponse, ListResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _user_out(row) -> UserOut:
    return UserOut(
        username=row["Username"], name=row["NombreVisible"], role=row["Rol"],
        role_label=ROLE_LABELS.get(row["Rol"], row["Rol"]), permissions=permissions_for(row["Rol"]),
        active=bool(row["Activo"]), last_login=row["UltimoAcceso"],
    )


@router.get("/config")
def auth_config():
    """Público: indica a la SPA si debe pedir login y qué permisos tiene cada rol."""
    return {
        "authEnabled": get_settings().auth.enabled,
        "roles": {role: {"label": ROLE_LABELS[role], "permissions": sorted(perms)}
                  for role, perms in ROLE_PERMISSIONS.items()},
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, conn: sqlite3.Connection = Depends(get_db)):
    return service.login(conn, payload.username, payload.password)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(username=user.username, name=user.name, role=user.role,
                   role_label=ROLE_LABELS.get(user.role, user.role), permissions=user.permissions)


@router.get("/users", response_model=ListResponse[UserOut], dependencies=[Depends(require_admin)])
def list_users(conn: sqlite3.Connection = Depends(get_db)):
    users = [_user_out(r) for r in repository.list_users(conn)]
    return ListResponse[UserOut](data=users, count=len(users))


@router.post("/users", response_model=ItemResponse[UserOut], status_code=201, dependencies=[Depends(require_admin)])
def create_user(payload: UserCreate, conn: sqlite3.Connection = Depends(get_db)):
    row = repository.create_user(conn, payload.username, payload.password, payload.role, payload.name)
    return ItemResponse[UserOut](data=_user_out(row), message="Usuario creado")


@router.patch("/users/{username}", response_model=ItemResponse[UserOut])
def update_user(username: str, payload: UserUpdate, conn: sqlite3.Connection = Depends(get_db),
                admin: CurrentUser = Depends(require_admin)):
    # Un administrador no puede quitarse a sí mismo el rol ni desactivarse (evita quedar sin admins)
    if username.lower() == admin.username.lower() and (payload.role == "user" or payload.active is False):
        raise ForbiddenError("No puede quitarse su propio rol de administrador ni desactivarse")
    row = repository.update_user(conn, username, role=payload.role, active=payload.active,
                                 password=payload.password, name=payload.name)
    return ItemResponse[UserOut](data=_user_out(row), message="Usuario actualizado")
