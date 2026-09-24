"""
Esquema relacional de las tablas crudas del HIS (Sistema de Información Hospitalaria).

Única fuente de verdad del DDL de las 7 tablas que llegan en los archivos planos
de data/. Lo usan el script de carga inicial (setup_db.py), la carga incremental
(POST /api/upload/{type}) y la capa semántica cuando la base está vacía.

Los nombres de tablas y columnas se conservan en español porque replican el
extracto original del HIS (es el contrato con los archivos de origen).
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

# Orden estricto de inserción: un Ingreso referencia a un Paciente y a un Triage.
LOAD_ORDER: list[str] = [
    "Paciente", "Triage", "Ingresos",
    "Atencion", "MedicamentoInsumo", "Servicios", "ProgramacionCirugia",
]

# Columnas AUTOINCREMENT: no vienen en los archivos del HIS, las genera SQLite.
AUTOINCREMENT_COLUMNS = frozenset({"IdAtencion", "IdProgramacion"})

# Tipos declarados que se tratan como texto al limpiar los datos.
TEXT_DECLARED_TYPES = ("TEXT", "DATE", "DATETIME")

SCHEMA_SQL = """
CREATE TABLE Paciente (
    IdPaciente INTEGER PRIMARY KEY,
    TipoDocumento TEXT,
    NombrePaciente TEXT,
    FechaNacimiento DATE,
    Sexo TEXT,
    Asegurador TEXT,
    Regimen TEXT,
    Departamento TEXT,
    Municipio TEXT,
    Zona TEXT
);

CREATE TABLE Triage (
    OidTriage INTEGER PRIMARY KEY,
    FechaTriage DATETIME,
    MotivoConsulta TEXT,
    TensionArterial TEXT,
    FrecuenciaCardiaca TEXT,
    FrecuenciaRespiratoria TEXT,
    Temperatura TEXT,
    IdPaciente2 INTEGER,
    CodigoTriage TEXT,
    ClasificacionTriage TEXT,
    FOREIGN KEY(IdPaciente2) REFERENCES Paciente(IdPaciente)
);

CREATE TABLE Ingresos (
    OidIngreso INTEGER PRIMARY KEY,
    ConsecutivoIngreso TEXT,
    IdPaciente INTEGER,
    ClaseIngreso TEXT,
    ViaIngreso TEXT,
    TipoRiesgo TEXT,
    FechaIngreso DATETIME,
    FechaHospitalizacion DATETIME,
    OidTriageA INTEGER,
    CodigoCama TEXT,
    NombreCama TEXT,
    NombreGrupoCama TEXT,
    NombreSubgrupoCama TEXT,
    CodigoDiagnostico TEXT,
    NombreDiagnostico TEXT,
    FOREIGN KEY(IdPaciente) REFERENCES Paciente(IdPaciente),
    FOREIGN KEY(OidTriageA) REFERENCES Triage(OidTriage)
);

CREATE TABLE Atencion (
    IdAtencion INTEGER PRIMARY KEY AUTOINCREMENT,
    OidIngreso INTEGER,
    FechaAtencion DATETIME,
    FOREIGN KEY(OidIngreso) REFERENCES Ingresos(OidIngreso)
);

CREATE TABLE ProgramacionCirugia (
    IdProgramacion INTEGER PRIMARY KEY AUTOINCREMENT,
    ConsecutivoProgramacion TEXT,
    IdPaciente INTEGER,
    OidIngreso INTEGER,
    CodigoServicio TEXT,
    FOREIGN KEY(IdPaciente) REFERENCES Paciente(IdPaciente),
    FOREIGN KEY(OidIngreso) REFERENCES Ingresos(OidIngreso)
);

CREATE TABLE Servicios (
    OidS INTEGER PRIMARY KEY,
    OidIngreso INTEGER,
    CodigoServicio TEXT,
    NombreServicio TEXT,
    Cantidad REAL,
    FechaPrestacion DATETIME,
    CodigoAreaServicio TEXT,
    AreaServicio TEXT,
    Especialidad TEXT,
    FOREIGN KEY(OidIngreso) REFERENCES Ingresos(OidIngreso)
);

CREATE TABLE MedicamentoInsumo (
    OidMI INTEGER PRIMARY KEY,
    OidIngreso INTEGER,
    CodigoServicio TEXT,
    NombreServicio TEXT,
    Cantidad REAL,
    FechaPrestacion DATETIME,
    AreaServicio TEXT,
    Especialidad TEXT,
    FOREIGN KEY(OidIngreso) REFERENCES Ingresos(OidIngreso)
);

-- Índices para optimizar JOINs (llaves foráneas)
CREATE INDEX idx_triage_paciente ON Triage(IdPaciente2);
CREATE INDEX idx_ingreso_paciente ON Ingresos(IdPaciente);
CREATE INDEX idx_ingreso_triage ON Ingresos(OidTriageA);
CREATE INDEX idx_atencion_ingreso ON Atencion(OidIngreso);
CREATE INDEX idx_prog_cirugia_paciente ON ProgramacionCirugia(IdPaciente);
CREATE INDEX idx_prog_cirugia_ingreso ON ProgramacionCirugia(OidIngreso);
CREATE INDEX idx_servicios_ingreso ON Servicios(OidIngreso);
CREATE INDEX idx_medicamentos_ingreso ON MedicamentoInsumo(OidIngreso);

-- Índices para filtros de tiempo y consultas comunes
CREATE INDEX idx_ingresos_fecha ON Ingresos(FechaIngreso);
CREATE INDEX idx_triage_fecha ON Triage(FechaTriage);
"""


@lru_cache(maxsize=None)
def get_declared_types(table_name: str) -> dict[str, str]:
    """
    Tipo declarado en SCHEMA_SQL para cada columna de la tabla (TEXT, INTEGER, DATETIME...).

    Se obtiene creando el esquema en una BD en memoria en lugar de parsear el DDL a
    mano: así nunca se desincroniza del SQL real.
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SCHEMA_SQL)
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    finally:
        conn.close()
    return {row[1]: (row[2] or "").upper() for row in rows}


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Columnas reales de una tabla en la base de datos abierta."""
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def his_tables_exist(conn: sqlite3.Connection) -> bool:
    """True si las 7 tablas del HIS ya existen (setup_db.py se ejecutó al menos una vez)."""
    found = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return all(table in found for table in LOAD_ORDER)


def create_schema(conn: sqlite3.Connection) -> None:
    """Borra las tablas del HIS (si existen) y crea el esquema relacional limpio."""
    cursor = conn.cursor()
    for table in reversed(LOAD_ORDER):
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.executescript(SCHEMA_SQL)
    conn.commit()
