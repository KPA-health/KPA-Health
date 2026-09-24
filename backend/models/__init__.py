"""
Capa MODELO (MVC): todo el acceso a SQLite vive aquí.

- db_connection.py   Única puerta de entrada a la BD (lectura/escritura y solo lectura).
- his_schema.py      DDL de las tablas crudas del HIS y orden de carga.
- semantic_layer.py  Tablas operativas, vistas y tablas materializadas de negocio.
- seed_data.py       Datos semilla (mapa de servicios, médicos y citas demo).
- *_model.py         Un módulo por entidad: consultas SQL + reglas de negocio,
                     y conversión de filas a DTOs de backend/schemas.

Los controladores nunca escriben SQL: siempre llaman a un modelo.
"""
