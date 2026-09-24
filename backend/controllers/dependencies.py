"""
Dependencias de FastAPI para proteger los controladores (autenticación + RBAC).

    router = APIRouter(dependencies=[Depends(require_permission(PERM_DASHBOARD))])
    @router.delete(..., dependencies=[Depends(require_permission(PERM_OPERATIONS))])

Con AUTH_ENABLED=false todas las peticiones actúan como un administrador
(útil para pruebas y demos sin login).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import jwt
from fastapi import Depends, Header

from backend.core.config import get_settings
from backend.core.errors import ForbiddenError, UnauthorizedError
from backend.models import user_model
from backend.models.db_connection import closing_connection
from backend.services.auth.permissions import PERM_USERS, ROLE_ADMIN, has_permission, permissions_for
from backend.services.auth.token_service import decode_access_token


@dataclass(frozen=True)
class CurrentUser:
    """Usuario autenticado de la petición en curso."""
    username: str
    name: str
    role: str

    @property
    def permissions(self) -> list[str]:
        return permissions_for(self.role)


ANONYMOUS_ADMIN = CurrentUser("sin-autenticacion", "Acceso libre (AUTH_ENABLED=false)", ROLE_ADMIN)


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """
    Valida el encabezado `Authorization: Bearer <JWT>` y devuelve el usuario.

    El rol se relee de la BD en cada petición (y no del token) para que desactivar
    a un usuario o cambiar su rol tenga efecto inmediato, sin esperar a que expire el JWT.
    """
    if not get_settings().auth.enabled:
        return ANONYMOUS_ADMIN
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Inicie sesión para continuar")
    try:
        claims = decode_access_token(token.strip())
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("La sesión expiró. Inicie sesión de nuevo") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token de acceso inválido") from exc

    with closing_connection() as conn:
        user = user_model.get_user(conn, claims["sub"])
    if user is None or not user["Activo"]:
        raise UnauthorizedError("El usuario no existe o está desactivado")
    return CurrentUser(user["Username"], user["NombreVisible"], user["Rol"])


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    """Fábrica de dependencias: exige que el rol del usuario tenga `permission` (si no, 403)."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user.role, permission):
            raise ForbiddenError("No tiene permisos para acceder a este módulo", {"required": permission})
        return user

    # Nombre único: FastAPI/OpenAPI distingue así cada dependencia generada
    dependency.__name__ = f"require_{permission}"
    return dependency


require_admin = require_permission(PERM_USERS)
