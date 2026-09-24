"""
Dependencias de FastAPI para proteger rutas.

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

from backend.auth import repository
from backend.auth.permissions import ROLE_ADMIN, has_permission, permissions_for
from backend.auth.service import AuthenticationError
from backend.auth.tokens import decode_access_token
from backend.core.config import get_settings
from backend.core.database import closing_connection
from backend.core.errors import AppError


class ForbiddenError(AppError):
    status_code = 403


@dataclass(frozen=True)
class CurrentUser:
    username: str
    name: str
    role: str

    @property
    def permissions(self) -> list[str]:
        return permissions_for(self.role)


ANONYMOUS_ADMIN = CurrentUser("sin-autenticacion", "Acceso libre (AUTH_ENABLED=false)", ROLE_ADMIN)


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not get_settings().auth.enabled:
        return ANONYMOUS_ADMIN
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Inicie sesión para continuar")
    try:
        claims = decode_access_token(token.strip())
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("La sesión expiró. Inicie sesión de nuevo") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token de acceso inválido") from exc

    # El usuario debe seguir existiendo y activo; el rol se toma de la BD (un cambio de rol aplica de inmediato)
    with closing_connection() as conn:
        user = repository.get_user(conn, claims["sub"])
    if user is None or not user["Activo"]:
        raise AuthenticationError("El usuario no existe o está desactivado")
    return CurrentUser(user["Username"], user["NombreVisible"], user["Rol"])


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user.role, permission):
            raise ForbiddenError("No tiene permisos para acceder a este módulo", {"required": permission})
        return user

    dependency.__name__ = f"require_{permission}"
    return dependency


require_admin = require_permission("users")
