"""
Autenticación y autorización (JWT + control de acceso basado en roles, RBAC).

- password_hasher.py  Hash de contraseñas PBKDF2-SHA256 (stdlib, sin dependencias nativas).
- token_service.py    Emisión y validación de JWT (HS256, PyJWT).
- permissions.py      Matriz rol -> permisos (única fuente de verdad; la SPA la recibe por /auth/config).
- auth_service.py     Caso de uso de login con bloqueo temporal tras intentos fallidos.

La persistencia de usuarios está en backend/models/user_model.py y las dependencias
de FastAPI que protegen las rutas en backend/controllers/dependencies.py.
"""
