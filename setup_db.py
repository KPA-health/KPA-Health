import pandas as pd
import sqlite3
import os

# 1. Conectar a la base de datos (crea el archivo hospital.db)
conn = sqlite3.connect('hospital.db')
cursor = conn.cursor()

print("1. Construyendo la arquitectura relacional (Tablas y Llaves)...")

# Borrar tablas si ya existen para empezar en limpio
tablas = ['ProgramacionCirugia', 'Servicios', 'MedicamentoInsumo', 'Atencion', 'Ingresos', 'Triage', 'Paciente']
for t in tablas:
    cursor.execute(f"DROP TABLE IF EXISTS {t}")

# 2. CREACIÓN DE TABLAS (Esquema estricto para que la IA entienda las relaciones)
esquema_sql = """
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
# Ejecutar la creación de la estructura
cursor.executescript(esquema_sql)
conn.commit()

# 3. ORDEN ESTRICTO DE INSERCIÓN
# ¡Muy importante! No podemos insertar un Ingreso si el Paciente no existe primero.
orden_archivos = [
    'Paciente', 'Triage', 'Ingresos', 
    'Atencion', 'MedicamentoInsumo', 'Servicios', 'ProgramacionCirugia'
]

print("\n2. Iniciando limpieza e inyección de datos...")

for archivo in orden_archivos:
    ruta = f'data/{archivo}.txt'
    if not os.path.exists(ruta):
        print(f"⚠️ Archivo no encontrado: {ruta}")
        continue
        
    print(f"-> Procesando e inyectando: {archivo}...")
    
    # Leer el archivo txt
    df = pd.read_csv(ruta, sep='|', encoding='utf-8', low_memory=False)
    
    # Limpieza estándar
    df.columns = df.columns.str.strip()
    df.drop_duplicates(inplace=True)
    
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace(['nan', 'NaN', 'None', '', 'NaT'], 'No Registrado')
        else:
            df[col] = df[col].fillna(0)

    # Limpieza específica
    if archivo == 'Paciente':
        df['NombrePaciente'] = 'Paciente_' + df['IdPaciente'].astype(str)
        df['FechaNacimiento'] = pd.to_datetime(df['FechaNacimiento'], errors='coerce')
    elif archivo == 'Ingresos':
        df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
        df['FechaHospitalizacion'] = pd.to_datetime(df['FechaHospitalizacion'], errors='coerce')

    # INSERTAR DATOS EN LA TABLA YA ESTRUCTURADA
    # Usamos if_exists='append' para que Pandas agregue los datos a la tabla relacional que creamos arriba, en lugar de borrarla.
    df.to_sql(archivo, conn, if_exists='append', index=False)
    
    print(f"   ✔️ {len(df)} registros insertados exitosamente.")

conn.close()
print("\n¡Operación exitosa! Base de datos relacional creada y limpia.")