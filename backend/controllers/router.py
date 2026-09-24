"""
Ensamblado de controladores.

Todas las rutas se publican en /api/* y, como alias, en /v1/* (sin duplicarse en
Swagger). Cada módulo exige un permiso según el rol del usuario autenticado con
JWT (ver backend/services/auth/permissions.py):

    admin -> todo
    user  -> dashboard, asistente IA y gestión de ingresos
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.controllers import (
    appointment_controller, assistant_controller, auth_controller, bed_controller, dashboard_controller,
    doctor_controller, insights_controller, patient_controller, pharmacy_controller, system_controller, upload_controller,
)
from backend.controllers.dependencies import require_permission
from backend.services.auth.permissions import PERM_ADMISSIONS, PERM_ASSISTANT, PERM_DASHBOARD, PERM_DATA

API_PREFIXES = (("/api", True), ("/v1", False))   # (prefijo, visible en Swagger)

# Controladores públicos o que gestionan su propia autenticación
PUBLIC_ROUTERS = [auth_controller.router, system_controller.router]

# Control de acceso por módulo (RBAC). Las acciones de administración dentro de cada
# módulo (borrar pacientes, cambiar estado de camas o stock) exigen además PERM_OPERATIONS.
PROTECTED_ROUTERS: list[tuple[APIRouter, str]] = [
    (dashboard_controller.dashboard_router, PERM_DASHBOARD),
    (dashboard_controller.stats_router, PERM_DASHBOARD),
    (insights_controller.router, PERM_DASHBOARD),
    (pharmacy_controller.router, PERM_DASHBOARD),
    (patient_controller.router, PERM_ADMISSIONS),
    (bed_controller.router, PERM_ADMISSIONS),
    (doctor_controller.router, PERM_ADMISSIONS),
    (appointment_controller.router, PERM_ADMISSIONS),
    (assistant_controller.router, PERM_ASSISTANT),
    (upload_controller.router, PERM_DATA),
]


def build_api_router() -> APIRouter:
    """Router raíz con todos los controladores bajo cada prefijo."""
    api_router = APIRouter()
    for prefix, in_schema in API_PREFIXES:
        for router in PUBLIC_ROUTERS:
            api_router.include_router(router, prefix=prefix, include_in_schema=in_schema)
        for router, permission in PROTECTED_ROUTERS:
            api_router.include_router(
                router, prefix=prefix, include_in_schema=in_schema,
                dependencies=[Depends(require_permission(permission))],
            )
    return api_router


api_router = build_api_router()
