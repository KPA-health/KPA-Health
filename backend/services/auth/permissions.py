"""
Matriz de roles y permisos (RBAC).

    admin -> todo
    user  -> dashboard, asistente IA y gestión de ingresos
"""
from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_USER = "user"

PERM_DASHBOARD = "dashboard"        # Dashboard BI y KPIs
PERM_ASSISTANT = "assistant"        # Asistente IA (consultas y voz)
PERM_ADMISSIONS = "admissions"      # Gestión de ingresos (wizard, camas, médicos)
PERM_DATA = "data"                  # Gestión de datos (carga de datasets del HIS)
PERM_SETTINGS = "settings"          # Configuración de la API REST
PERM_USERS = "users"                # Administración de usuarios
PERM_OPERATIONS = "operations"      # Cambios operativos: estado de camas, stock, borrar registros

ALL_PERMISSIONS = (PERM_DASHBOARD, PERM_ASSISTANT, PERM_ADMISSIONS, PERM_DATA,
                   PERM_SETTINGS, PERM_USERS, PERM_OPERATIONS)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: frozenset(ALL_PERMISSIONS),
    ROLE_USER: frozenset({PERM_DASHBOARD, PERM_ASSISTANT, PERM_ADMISSIONS}),
}

ROLE_LABELS = {ROLE_ADMIN: "Administrador", ROLE_USER: "Usuario"}


def permissions_for(role: str) -> list[str]:
    """Permisos del rol en orden alfabético (lista vacía si el rol no existe)."""
    return sorted(ROLE_PERMISSIONS.get(role, frozenset()))


def has_permission(role: str, permission: str) -> bool:
    """True si el rol incluye el permiso."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
