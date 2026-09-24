"""
Ensamblado de rutas.

Todas las rutas se publican en /api/* y, como alias, en /v1/*.
Cada módulo exige un permiso según el rol del usuario autenticado con JWT
(ver backend/auth/permissions.py):
    admin -> todo
    user  -> dashboard, asistente IA y gestión de ingresos
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.routes import ai, auth, operations, patients, staff, system, uploads
from backend.auth.dependencies import require_permission
from backend.auth.permissions import PERM_ADMISSIONS, PERM_ASSISTANT, PERM_DASHBOARD, PERM_DATA


def _protected(router: APIRouter, permission: str) -> tuple[APIRouter, list]:
    return router, [Depends(require_permission(permission))]


# Control de acceso por módulo (RBAC). Las acciones de administración dentro de cada
# módulo (borrar pacientes, cambiar estado de camas o stock) exigen además PERM_OPERATIONS.
PROTECTED = [
    _protected(operations.dashboard_router, PERM_DASHBOARD),
    _protected(operations.stats_router, PERM_DASHBOARD),
    _protected(operations.pharmacy_router, PERM_DASHBOARD),
    _protected(patients.router, PERM_ADMISSIONS),
    _protected(operations.rooms_router, PERM_ADMISSIONS),
    _protected(staff.doctors_router, PERM_ADMISSIONS),
    _protected(staff.appointments_router, PERM_ADMISSIONS),
    _protected(ai.router, PERM_ASSISTANT),
    _protected(uploads.router, PERM_DATA),
]

api_router = APIRouter()
for prefix, in_schema in (("/api", True), ("/v1", False)):
    api_router.include_router(auth.router, prefix=prefix, include_in_schema=in_schema)
    api_router.include_router(system.router, prefix=prefix, include_in_schema=in_schema)
    for router, dependencies in PROTECTED:
        api_router.include_router(router, prefix=prefix, dependencies=dependencies, include_in_schema=in_schema)
