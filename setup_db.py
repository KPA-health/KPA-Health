"""
Script ETL: construye hospital.db a partir de los archivos planos de data/.

Uso:
    python setup_db.py

Las funciones de este módulo (esquema, orden de carga y limpieza con Pandas) son
la única fuente de verdad del ETL: el backend las reutiliza en
POST /api/upload/{type} para que una carga incremental aplique exactamente la
misma limpieza que la carga inicial.
"""
import os
import sqlite3
from functools import lru_cache

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hospital.db')
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Tablas del HIS en orden estricto de inserción:
# no se puede insertar un Ingreso si el Paciente no existe primero.
LOAD_ORDER = [
    'Paciente', 'Triage', 'Ingresos',
    'Atencion', 'MedicamentoInsumo', 'Servicios', 'ProgramacionCirugia'
]

MISSING_TEXT_TOKENS = ['nan', 'NaN', 'None', '', 'NaT']
MISSING_TEXT_VALUE = 'No Registrado'

# Esquema estricto para que la IA entienda las relaciones
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

-- Índices para optimizar JOINs (Llaves Foráneas)
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


TEXT_DECLARED_TYPES = ('TEXT', 'DATE', 'DATETIME')


@lru_cache(maxsize=None)
def declared_types(table_name: str) -> dict[str, str]:
    """Tipo declarado en SCHEMA_SQL para cada columna de la tabla (TEXT, INTEGER, DATETIME...)."""
    conn = sqlite3.connect(':memory:')
    try:
        conn.executescript(SCHEMA_SQL)
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    finally:
        conn.close()
    return {row[1]: (row[2] or '').upper() for row in rows}


def is_text_column(series: pd.Series, declared_type: str = '') -> bool:
    """
    True si la columna es de texto: por su tipo en pandas 2 (object) o pandas 3 (str),
    o por el tipo declarado en el esquema (cubre columnas de texto que llegan
    completamente vacías y pandas infiere como numéricas).
    """
    return (
        declared_type in TEXT_DECLARED_TYPES
        or pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    )


def read_source_file(source) -> pd.DataFrame:
    """Lee un archivo plano del HIS (separado por '|'). Acepta ruta o buffer binario."""
    return pd.read_csv(source, sep='|', encoding='utf-8', low_memory=False)


def clean_dataframe(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Limpieza estándar + reglas específicas por tabla. Devuelve un DataFrame nuevo."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = df.drop_duplicates()
    types = declared_types(table_name)

    for col in df.columns:
        if is_text_column(df[col], types.get(col, '')):
            # fillna explícito: en pandas 3 astype(str) conserva los NaN
            df[col] = df[col].fillna(MISSING_TEXT_VALUE).astype(str).str.strip()
            df[col] = df[col].replace(MISSING_TEXT_TOKENS, MISSING_TEXT_VALUE)
        else:
            df[col] = df[col].fillna(0)

    # Limpieza específica
    if table_name == 'Paciente':
        # Anonimización: el nombre real nunca entra a la base de datos
        df['NombrePaciente'] = 'Paciente_' + df['IdPaciente'].astype(str)
        df['FechaNacimiento'] = pd.to_datetime(df['FechaNacimiento'], errors='coerce')
    elif table_name == 'Ingresos':
        df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
        df['FechaHospitalizacion'] = pd.to_datetime(df['FechaHospitalizacion'], errors='coerce')

    return df


def create_schema(conn: sqlite3.Connection) -> None:
    """Borra las tablas del HIS (si existen) y crea el esquema relacional limpio."""
    cursor = conn.cursor()
    for table in reversed(LOAD_ORDER):
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.executescript(SCHEMA_SQL)
    conn.commit()


def load_all(conn: sqlite3.Connection, data_dir: str = DATA_DIR) -> None:
    """Lee, limpia e inserta cada archivo de data/ en su tabla ya estructurada."""
    for table in LOAD_ORDER:
        path = os.path.join(data_dir, f'{table}.txt')
        if not os.path.exists(path):
            print(f"⚠️ Archivo no encontrado: {path}")
            continue

        print(f"-> Procesando e inyectando: {table}...")
        df = clean_dataframe(read_source_file(path), table)
        # if_exists='append' para respetar la tabla relacional creada arriba
        df.to_sql(table, conn, if_exists='append', index=False)
        print(f"   ✔️ {len(df)} registros insertados exitosamente.")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        print("1. Construyendo la arquitectura relacional (Tablas y Llaves)...")
        create_schema(conn)
        print("\n2. Iniciando limpieza e inyección de datos...")
        load_all(conn)
    finally:
        conn.close()
    print("\n¡Operación exitosa! Base de datos relacional creada y limpia.")
    print("La capa semántica (vistas y tablas derivadas) la construye el backend al arrancar.")


if __name__ == '__main__':
    main()
