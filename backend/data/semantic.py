import sqlite3
import json
import logging
from backend.settings import settings

def init_views(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Admissions view
    cursor.execute("DROP VIEW IF EXISTS v_admissions_daily")
    cursor.execute("""
        CREATE VIEW v_admissions_daily AS
        SELECT 
            i.OidIngreso as admission_id,
            p.IdPaciente as patient_id,
            date(i.FechaIngreso) as admission_date,
            i.FechaIngreso as admission_timestamp,
            i.ViaIngreso as admission_route,
            i.ClaseIngreso as admission_class,
            t.CodigoTriage as triage_code,
            t.ClasificacionTriage as triage_class,
            i.CodigoCama as bed_code,
            i.NombreCama as bed_name,
            i.NombreGrupoCama as bed_group,
            i.NombreSubgrupoCama as bed_subgroup
        FROM Ingresos i
        JOIN Paciente p ON i.IdPaciente = p.IdPaciente
        LEFT JOIN Triage t ON i.OidTriageA = t.OidTriage
    """)

    # Triage view
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_triage_daily AS
        SELECT 
            OidTriage as triage_id,
            date(FechaTriage) as triage_date,
            FechaTriage as triage_timestamp,
            CodigoTriage as triage_code,
            ClasificacionTriage as triage_class
        FROM Triage
    """)

    # Wait daily view (Espera desde ingreso: cohorte por FechaIngreso, unir primera atencion)
    # Using a CTE to get the first attention for each admission
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_wait_daily AS
        WITH FirstAttention AS (
            SELECT 
                OidIngreso, 
                MIN(FechaAtencion) as first_attention_time
            FROM Atencion
            GROUP BY OidIngreso
        )
        SELECT 
            i.OidIngreso as admission_id,
            date(i.FechaIngreso) as admission_date,
            i.FechaIngreso as admission_timestamp,
            fa.first_attention_time as attention_timestamp,
            (julianday(fa.first_attention_time) - julianday(i.FechaIngreso)) * 24 * 60 as wait_minutes,
            t.CodigoTriage as triage_code
        FROM Ingresos i
        LEFT JOIN FirstAttention fa ON i.OidIngreso = fa.OidIngreso
        LEFT JOIN Triage t ON i.OidTriageA = t.OidTriage
    """)

    # Medication view
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_medication_daily AS
        SELECT 
            OidMI as medication_id,
            OidIngreso as admission_id,
            date(FechaPrestacion) as delivery_date,
            FechaPrestacion as delivery_timestamp,
            CodigoServicio as medication_code,
            NombreServicio as medication_name,
            Cantidad as quantity
        FROM MedicamentoInsumo
    """)

    # Services view (Servicios distinguen unidades de episodios unicos)
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_services_daily AS
        SELECT 
            OidS as service_id,
            OidIngreso as admission_id,
            date(FechaPrestacion) as service_date,
            FechaPrestacion as service_timestamp,
            CodigoServicio as service_code,
            NombreServicio as service_name,
            Cantidad as quantity,
            Especialidad as specialty
        FROM Servicios
    """)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_views(settings.db_path)
    print("Views initialized.")
