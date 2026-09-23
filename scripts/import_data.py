import pandas as pd
import sqlite3
import os
import csv
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def create_schema(conn):
    cursor = conn.cursor()
    # Staging tables
    esquema_sql = """
    CREATE TABLE IF NOT EXISTS Paciente (
        TipoDocumento TEXT, 
        IdPaciente INTEGER PRIMARY KEY,
        NombrePaciente TEXT, 
        FechaNacimiento DATE, 
        Sexo TEXT, 
        Asegurador TEXT, 
        Regimen TEXT, 
        Departamento TEXT, 
        Municipio TEXT, 
        Zona TEXT
    );

    CREATE TABLE IF NOT EXISTS Triage (
        OidTriage INTEGER PRIMARY KEY,
        FechaTriage DATETIME, 
        MotivoConsulta TEXT, 
        TensionArterial TEXT, 
        FrecuenciaCardiaca TEXT, 
        FrecuenciaRespiratoria TEXT, 
        Temperatura TEXT, 
        IdPaciente2 INTEGER, 
        CodigoTriage TEXT, 
        ClasificacionTriage TEXT
    );

    CREATE TABLE IF NOT EXISTS Ingresos (
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
        NombreDiagnostico TEXT
    );

    CREATE TABLE IF NOT EXISTS Atencion (
        OidIngreso INTEGER, 
        FechaAtencion DATETIME
    );

    CREATE TABLE IF NOT EXISTS ProgramacionCirugia (
        ConsecutivoProgramacion TEXT, 
        IdPaciente INTEGER, 
        OidIngreso INTEGER, 
        CodigoServicio TEXT
    );

    CREATE TABLE IF NOT EXISTS Servicios (
        OidIngreso INTEGER, 
        CodigoServicio TEXT, 
        NombreServicio TEXT, 
        Cantidad REAL, 
        FechaPrestacion DATETIME, 
        CodigoAreaServicio TEXT, 
        AreaServicio TEXT, 
        Especialidad TEXT,
        OidS INTEGER PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS MedicamentoInsumo (
        OidIngreso INTEGER, 
        CodigoServicio TEXT, 
        NombreServicio TEXT, 
        Cantidad REAL, 
        FechaPrestacion DATETIME, 
        AreaServicio TEXT, 
        Especialidad TEXT,
        OidMI INTEGER PRIMARY KEY
    );
    """
    cursor.executescript(esquema_sql)
    conn.commit()

def import_table(conn, table_name, file_path):
    logging.info(f"Importing {table_name} from {file_path}")
    if not os.path.exists(file_path):
        logging.error(f"File {file_path} not found.")
        return
    
    # Read with explicit quotes
    df = pd.read_csv(file_path, sep='|', encoding='utf-8', 
                     quoting=csv.QUOTE_NONE, dtype=str)
    
    logging.info(f"Rows read: {len(df)}")
    
    # Trim column names
    df.columns = df.columns.str.strip()
    
    # Clean string columns
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(['nan', 'NaN', 'None', ''], None)
    
    # Specific cleaning rules as per requirements
    if table_name == 'Triage':
        # Split empty rows. OidTriage is null.
        valid_triage = df[df['OidTriage'].notna()].copy()
        logging.info(f"Valid Triage rows (OidTriage not null): {len(valid_triage)}")
        valid_triage = valid_triage.drop_duplicates(subset=['OidTriage'])
        logging.info(f"Valid Triage rows after dup drop: {len(valid_triage)}")
        valid_triage.to_sql(table_name, conn, if_exists='append', index=False)
        return

    # Drop true duplicates for others if needed
    if table_name == 'ProgramacionCirugia':
        # EDA says 276 duplicates for complete rows
        df = df.drop_duplicates()
        logging.info(f"Rows after dropping exact duplicates: {len(df)}")
    
    df.to_sql(table_name, conn, if_exists='append', index=False)

def main():
    db_path = 'hospital_validated.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    
    orden_archivos = [
        ('Paciente', 'Datos/Paciente.txt'),
        ('Triage', 'Datos/Triage.txt'),
        ('Ingresos', 'Datos/Ingresos.txt'),
        ('Atencion', 'Datos/Atencion.txt'),
        ('MedicamentoInsumo', 'Datos/MedicamentoInsumo.txt'),
        ('Servicios', 'Datos/Servicios.txt'),
        ('ProgramacionCirugia', 'Datos/ProgramacionCirugia.txt')
    ]
    
    for table, path in orden_archivos:
        import_table(conn, table, path)
        
    conn.close()
    logging.info("Import completed successfully into hospital_validated.db")

if __name__ == '__main__':
    main()
