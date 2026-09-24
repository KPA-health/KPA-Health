"""
Autenticación y autorización (JWT + control de acceso basado en roles, RBAC).

- passwords.py    Hash de contraseñas PBKDF2-SHA256 (stdlib, sin dependencias nativas).
- tokens.py       Emisión y validación de JWT (HS256, PyJWT).
- permissions.py  Matriz rol -> permisos (única fuente de verdad, la usa también la SPA).
- repository.py   Tabla Usuario (SQLite) y usuarios iniciales desde .env.
- service.py      Login con bloqueo temporal tras intentos fallidos.
- dependencies.py Dependencias de FastAPI: usuario actual, require_permission, require_admin.
"""
