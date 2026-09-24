"""
Capa CONTROLADOR (MVC): rutas HTTP de FastAPI.

Cada controlador recibe la petición (validada por los esquemas Pydantic), delega
en un modelo o servicio y arma la respuesta con el sobre que espera la SPA
({data, count, message}). No contiene SQL ni lógica de negocio; los errores de
dominio se propagan y los traduce backend/core/errors.py a códigos HTTP.

- router.py        Ensambla todos los controladores bajo /api y /v1 con RBAC por módulo.
- dependencies.py  Dependencias de seguridad (usuario actual, permisos).
"""
