"""
Capa semántica sobre las tablas crudas del HIS.

El extracto del HIS no trae estado de camas, fecha de egreso, stock de farmacia
ni personal médico. Esta capa los deriva de forma documentada para que la API
REST y el agente NL2SQL trabajen sobre conceptos de negocio:

Tablas operativas (las escribe la app, nunca las borra setup_db.py):
    ParametrosSistema, MapaServicio, IngresoGestion, CamaEstadoManual,
    Medico, Cita, InventarioFarmacia

Tablas materializadas (se recalculan tras cada carga de datos):
    ActividadIngreso  -> primera/última actividad clínica por ingreso
    OcupacionDiaria   -> camas ocupadas por servicio y día

Vistas (siempre coherentes con los datos):
    FechaReferencia, CatalogoCamas, VistaIngresos, EstadoCamas,
    EsperaUrgencias, CirugiasProgramadas
"""
from __future__ import annotations

import logging
import math
import sqlite3
import time
import zlib
from datetime import date, datetime, timedelta

import setup_db
from backend.core.config import get_settings
from backend.db.seed import DEMO_APPOINTMENTS, DEMO_DOCTORS, MAPA_SERVICIO

logger = logging.getLogger("medipulse.semantic")

REFERENCE_KEY = "momento_referencia"
SIGNATURE_KEY = "firma_datos"
REFRESHED_AT_KEY = "ultima_actualizacion"

UCI_SERVICE = "Cuidados Intensivos (UCI)"
SAFETY_STOCK_DAYS = 10  # StockMinimo = consumo diario promedio x 10 días

# --------------------------------------------------------------------------- #
# Fragmentos SQL reutilizables
# --------------------------------------------------------------------------- #


def triage_level_sql(col: str) -> str:
    """Extrae el nivel (1-5) de textos como 'CONSULTORIOS DIFERIDA - TRIAGE 3'."""
    return (
        f"CASE WHEN INSTR(UPPER({col}), 'TRIAGE') > 0 THEN NULLIF(CAST(SUBSTR({col}, "
        f"INSTR(UPPER({col}), 'TRIAGE') + 7, 1) AS INTEGER), 0) END"
    )


def shift_sql(col: str) -> str:
    """Turnos hospitalarios: Mañana 07-13, Tarde 13-19, Noche 19-07."""
    hour = f"CAST(strftime('%H', {col}) AS INTEGER)"
    return (
        f"CASE WHEN {col} IS NULL THEN NULL "
        f"WHEN {hour} BETWEEN 7 AND 12 THEN 'Mañana' "
        f"WHEN {hour} BETWEEN 13 AND 18 THEN 'Tarde' ELSE 'Noche' END"
    )


# --------------------------------------------------------------------------- #
# DDL
# --------------------------------------------------------------------------- #

OPERATIONAL_DDL = """
CREATE TABLE IF NOT EXISTS ParametrosSistema (
    Clave TEXT PRIMARY KEY,
    Valor TEXT,
    ActualizadoEn TEXT
);

CREATE TABLE IF NOT EXISTS MapaServicio (
    NombreGrupoCama TEXT PRIMARY KEY,
    Servicio TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS IngresoGestion (
    OidIngreso INTEGER PRIMARY KEY,
    Origen TEXT NOT NULL DEFAULT 'HIS',
    DocumentoIdentidad TEXT,      -- obsoleta: siempre NULL (el documento solo se guarda como hash)
    DocumentoHash TEXT,           -- HMAC-SHA256 del documento (búsqueda sin exponer el dato)
    Estado TEXT,
    Departamento TEXT,
    TipoSangre TEXT,
    Alergias TEXT,
    Telefono TEXT,
    SaturacionO2 TEXT,
    Notas TEXT,
    MedicoAsignadoId TEXT,
    MedicoAsignadoNombre TEXT,
    FechaAlta TEXT,
    NotasAlta TEXT,
    Eliminado INTEGER NOT NULL DEFAULT 0,
    ActualizadoEn TEXT
);

CREATE TABLE IF NOT EXISTS CamaEstadoManual (
    CodigoCama TEXT PRIMARY KEY,
    Estado TEXT NOT NULL,
    IdPacienteApp TEXT,
    NombrePacienteApp TEXT,
    ActualizadoEn TEXT
);

CREATE TABLE IF NOT EXISTS Medico (
    IdMedico TEXT PRIMARY KEY,
    Nombre TEXT NOT NULL,
    Especialidad TEXT,
    Departamento TEXT,
    RegistroProfesional TEXT,
    Turno TEXT,
    Estado TEXT,
    Telefono TEXT,
    Email TEXT,
    Consultorio TEXT,
    Avatar TEXT,
    Origen TEXT NOT NULL DEFAULT 'Demo'
);

CREATE TABLE IF NOT EXISTS Cita (
    IdCita TEXT PRIMARY KEY,
    IdPacienteApp TEXT,
    NombrePaciente TEXT,
    IdMedico TEXT,
    NombreMedico TEXT,
    Especialidad TEXT,
    Fecha TEXT,
    Hora TEXT,
    Motivo TEXT,
    Estado TEXT NOT NULL DEFAULT 'Programada',
    Prioridad TEXT NOT NULL DEFAULT 'Normal',
    CreadoEn TEXT
);
CREATE INDEX IF NOT EXISTS idx_cita_fecha ON Cita(Fecha);

CREATE TABLE IF NOT EXISTS InventarioFarmacia (
    CodigoMedicamento TEXT PRIMARY KEY,
    NombreMedicamento TEXT,
    Categoria TEXT,
    Unidad TEXT,
    ConsumoTotal REAL,
    ConsumoUltimos30Dias REAL,
    ConsumoDiarioPromedio REAL,
    StockActual REAL,
    StockMinimo REAL,
    Lote TEXT,
    FechaVencimiento TEXT,
    StockSimulado INTEGER NOT NULL DEFAULT 1,
    ActualizadoEn TEXT,
    DiasInventario REAL GENERATED ALWAYS AS (
        CASE WHEN ConsumoDiarioPromedio > 0
             THEN ROUND(StockActual / ConsumoDiarioPromedio, 1) END
    ) VIRTUAL,
    Estado TEXT GENERATED ALWAYS AS (
        CASE WHEN StockMinimo > 0 AND StockActual <= StockMinimo * 0.5 THEN 'Crítico'
             WHEN StockMinimo > 0 AND StockActual <= StockMinimo THEN 'Bajo'
             ELSE 'Adecuado' END
    ) VIRTUAL
);

CREATE TABLE IF NOT EXISTS ActividadIngreso (
    OidIngreso INTEGER PRIMARY KEY,
    PrimeraActividad TEXT,
    UltimaActividad TEXT,
    NumeroRegistros INTEGER,
    EspecialidadPrincipal TEXT,
    FechaPrimerQuirofano TEXT,
    AreaQuirofano TEXT
);

CREATE TABLE IF NOT EXISTS OcupacionDiaria (
    Fecha TEXT NOT NULL,
    Servicio TEXT NOT NULL,
    CamasTotales INTEGER NOT NULL,
    CamasOcupadas INTEGER NOT NULL,
    PorcentajeOcupacion REAL NOT NULL,
    PRIMARY KEY (Fecha, Servicio)
);
"""

# Índices adicionales sobre tablas del HIS para las consultas del agente.
HIS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_servicios_fecha ON Servicios(FechaPrestacion);
CREATE INDEX IF NOT EXISTS idx_servicios_area ON Servicios(AreaServicio);
CREATE INDEX IF NOT EXISTS idx_medicamentos_fecha ON MedicamentoInsumo(FechaPrestacion);
CREATE INDEX IF NOT EXISTS idx_medicamentos_codigo ON MedicamentoInsumo(CodigoServicio);
CREATE INDEX IF NOT EXISTS idx_atencion_fecha ON Atencion(FechaAtencion);
"""

_VIEW_INGRESOS = f"""
CREATE VIEW VistaIngresos AS
SELECT
    x.*,
    CASE
        WHEN x.EstadoManual IS NOT NULL THEN x.EstadoManual
        WHEN x.Activo = 0 THEN 'Dado de Alta'
        WHEN x.NivelTriage = 1 OR x.Servicio = '{UCI_SERVICE}' THEN 'Crítico'
        WHEN x.ClaseIngreso = 'Hospitalario' THEN 'Internado'
        ELSE 'En Observación'
    END AS Estado,
    ROUND(julianday(CASE WHEN x.Activo = 1
                         THEN MAX(x.FechaFinEstimada, COALESCE(x.MomentoReferencia, x.FechaFinEstimada))
                         ELSE x.FechaFinEstimada END)
          - julianday(x.FechaInicioEstancia), 2) AS DiasEstancia
FROM (
    SELECT
        b.*,
        CASE
            WHEN b.EstadoManual = 'Dado de Alta' THEN 0
            WHEN b.EstadoManual IS NOT NULL OR b.Origen = 'App' THEN 1
            WHEN b.FechaFinEstimada < b.MomentoReferencia THEN 0
            ELSE 1
        END AS Activo
    FROM (
        SELECT
            i.OidIngreso,
            i.IdPaciente,
            COALESCE(g.Origen, 'HIS') AS Origen,
            p.Sexo,
            p.Regimen,
            p.Asegurador,
            p.Departamento AS DepartamentoResidencia,
            p.Municipio,
            p.Zona,
            CASE WHEN p.FechaNacimiento IS NOT NULL AND i.FechaIngreso IS NOT NULL
                 THEN CAST((julianday(i.FechaIngreso) - julianday(p.FechaNacimiento)) / 365.25 AS INTEGER)
            END AS Edad,
            i.ClaseIngreso,
            i.ViaIngreso,
            i.TipoRiesgo,
            i.FechaIngreso,
            i.FechaHospitalizacion,
            COALESCE(i.FechaHospitalizacion, i.FechaIngreso) AS FechaInicioEstancia,
            COALESCE(g.FechaAlta, a.UltimaActividad, i.FechaHospitalizacion, i.FechaIngreso) AS FechaFinEstimada,
            COALESCE(g.Departamento, m.Servicio, i.NombreGrupoCama) AS Servicio,
            i.NombreSubgrupoCama AS SubgrupoCama,
            i.CodigoCama,
            i.NombreCama,
            CASE WHEN i.NombreCama LIKE '%VIRTUAL%' OR i.CodigoCama IN ('No Registrado', '0', '')
                 THEN 1 ELSE 0 END AS CamaVirtual,
            i.CodigoDiagnostico,
            i.NombreDiagnostico,
            CASE WHEN t.FechaTriage GLOB '2*' THEN t.FechaTriage END AS FechaTriage,
            t.ClasificacionTriage,
            {triage_level_sql('t.ClasificacionTriage')} AS NivelTriage,
            {shift_sql('i.FechaIngreso')} AS TurnoIngreso,
            COALESCE(a.EspecialidadPrincipal, 'No Registrado') AS EspecialidadPrincipal,
            g.Estado AS EstadoManual,
            r.Momento AS MomentoReferencia
        FROM Ingresos i
        LEFT JOIN FechaReferencia r ON 1 = 1
        LEFT JOIN Paciente p ON p.IdPaciente = i.IdPaciente
        LEFT JOIN Triage t ON t.OidTriage = i.OidTriageA
        LEFT JOIN MapaServicio m ON m.NombreGrupoCama = i.NombreGrupoCama
        LEFT JOIN ActividadIngreso a ON a.OidIngreso = i.OidIngreso
        LEFT JOIN IngresoGestion g ON g.OidIngreso = i.OidIngreso
        WHERE COALESCE(g.Eliminado, 0) = 0
    ) b
) x
"""

# Orden importante: cada vista solo depende de las anteriores.
VIEWS: list[tuple[str, str]] = [
    ("FechaReferencia", f"""
CREATE VIEW FechaReferencia AS
SELECT DATE(Valor) AS Fecha, Valor AS Momento
FROM ParametrosSistema WHERE Clave = '{REFERENCE_KEY}'
"""),
    ("CatalogoCamas", """
CREATE VIEW CatalogoCamas AS
SELECT
    i.CodigoCama,
    MAX(i.NombreCama) AS NombreCama,
    MAX(i.NombreGrupoCama) AS GrupoCama,
    MAX(i.NombreSubgrupoCama) AS SubgrupoCama,
    COALESCE(MAX(m.Servicio), MAX(i.NombreGrupoCama)) AS Servicio
FROM Ingresos i
LEFT JOIN MapaServicio m ON m.NombreGrupoCama = i.NombreGrupoCama
WHERE i.CodigoCama NOT IN ('No Registrado', '0', '')
  AND i.NombreCama NOT LIKE '%VIRTUAL%'
GROUP BY i.CodigoCama
"""),
    ("VistaIngresos", _VIEW_INGRESOS),
    ("EstadoCamas", """
CREATE VIEW EstadoCamas AS
SELECT
    c.CodigoCama,
    c.NombreCama,
    c.Servicio,
    c.GrupoCama,
    c.SubgrupoCama,
    COALESCE(cm.Estado, CASE WHEN o.OidIngreso IS NOT NULL THEN 'Ocupada' ELSE 'Libre' END) AS Estado,
    CASE WHEN cm.Estado IS NULL OR cm.Estado = 'Ocupada' THEN o.OidIngreso END AS OidIngreso,
    CASE WHEN cm.Estado IS NULL OR cm.Estado = 'Ocupada' THEN o.IdPaciente END AS IdPaciente,
    CASE WHEN cm.Estado IS NULL OR cm.Estado = 'Ocupada' THEN o.FechaInicioEstancia END AS OcupadaDesde,
    CASE WHEN cm.Estado IS NOT NULL THEN 1 ELSE 0 END AS EstadoManual
FROM CatalogoCamas c
LEFT JOIN (
    SELECT CodigoCama, OidIngreso, IdPaciente, MAX(FechaInicioEstancia) AS FechaInicioEstancia
    FROM VistaIngresos
    WHERE Activo = 1 AND CamaVirtual = 0
    GROUP BY CodigoCama
) o ON o.CodigoCama = c.CodigoCama
LEFT JOIN CamaEstadoManual cm ON cm.CodigoCama = c.CodigoCama
"""),
    ("EsperaUrgencias", f"""
CREATE VIEW EsperaUrgencias AS
SELECT
    i.OidIngreso,
    i.IdPaciente,
    i.ViaIngreso,
    COALESCE(m.Servicio, i.NombreGrupoCama) AS Servicio,
    t.ClasificacionTriage,
    {triage_level_sql('t.ClasificacionTriage')} AS NivelTriage,
    t.FechaTriage,
    at.PrimeraAtencion AS FechaAtencion,
    DATE(t.FechaTriage) AS Fecha,
    {shift_sql('t.FechaTriage')} AS Turno,
    ROUND((julianday(at.PrimeraAtencion) - julianday(t.FechaTriage)) * 1440, 1) AS MinutosEspera
FROM Ingresos i
JOIN Triage t ON t.OidTriage = i.OidTriageA AND t.FechaTriage GLOB '2*'
JOIN (
    SELECT OidIngreso, MIN(FechaAtencion) AS PrimeraAtencion
    FROM Atencion WHERE FechaAtencion GLOB '2*'
    GROUP BY OidIngreso
) at ON at.OidIngreso = i.OidIngreso
LEFT JOIN MapaServicio m ON m.NombreGrupoCama = i.NombreGrupoCama
WHERE at.PrimeraAtencion >= t.FechaTriage
"""),
    ("CirugiasProgramadas", """
CREATE VIEW CirugiasProgramadas AS
SELECT
    pc.ConsecutivoProgramacion,
    NULLIF(pc.OidIngreso, 0) AS OidIngreso,
    pc.IdPaciente,
    COUNT(*) AS NumeroProcedimientos,
    CASE WHEN MAX(i.OidIngreso) IS NULL THEN 'Sin ingreso en el periodo'
         WHEN MAX(a.FechaPrimerQuirofano) IS NOT NULL THEN 'Realizada'
         ELSE 'No realizada' END AS EstadoCirugia,
    MAX(a.FechaPrimerQuirofano) AS FechaCirugia,
    DATE(MAX(a.FechaPrimerQuirofano)) AS Fecha,
    MAX(a.AreaQuirofano) AS AreaQuirofano,
    COALESCE(MAX(m.Servicio), MAX(i.NombreGrupoCama)) AS Servicio
FROM ProgramacionCirugia pc
LEFT JOIN Ingresos i ON i.OidIngreso = pc.OidIngreso
LEFT JOIN ActividadIngreso a ON a.OidIngreso = pc.OidIngreso
LEFT JOIN MapaServicio m ON m.NombreGrupoCama = i.NombreGrupoCama
GROUP BY pc.ConsecutivoProgramacion, pc.OidIngreso, pc.IdPaciente
"""),
]

VIEW_NAMES = [name for name, _ in VIEWS]

_REFRESH_ACTIVIDAD = """
DELETE FROM ActividadIngreso;
INSERT INTO ActividadIngreso (
    OidIngreso, PrimeraActividad, UltimaActividad, NumeroRegistros,
    EspecialidadPrincipal, FechaPrimerQuirofano, AreaQuirofano
)
WITH act AS (
    SELECT OidIngreso, FechaPrestacion AS Fecha FROM Servicios WHERE FechaPrestacion GLOB '2*'
    UNION ALL
    SELECT OidIngreso, FechaPrestacion FROM MedicamentoInsumo WHERE FechaPrestacion GLOB '2*'
    UNION ALL
    SELECT OidIngreso, FechaAtencion FROM Atencion WHERE FechaAtencion GLOB '2*'
),
rango AS (
    SELECT OidIngreso, MIN(Fecha) AS PrimeraActividad, MAX(Fecha) AS UltimaActividad,
           COUNT(*) AS NumeroRegistros
    FROM act GROUP BY OidIngreso
),
esp AS (
    SELECT OidIngreso, Especialidad FROM (
        SELECT OidIngreso, Especialidad,
               ROW_NUMBER() OVER (PARTITION BY OidIngreso ORDER BY COUNT(*) DESC) AS rn
        FROM Servicios
        WHERE Especialidad NOT IN ('No Registrado', 'MEDICINA GENERAL', 'TERAPIA RESPIRATORIA',
                                   'FISIOTERAPIA', 'FONOAUDIOLOGIA')
        GROUP BY OidIngreso, Especialidad
    ) WHERE rn = 1
),
qx AS (
    SELECT OidIngreso, MIN(FechaPrestacion) AS FechaPrimerQuirofano,
           MIN(AreaServicio) AS AreaQuirofano
    FROM Servicios
    WHERE AreaServicio LIKE 'QUIROFANOS%' AND FechaPrestacion GLOB '2*'
    GROUP BY OidIngreso
)
SELECT r.OidIngreso, r.PrimeraActividad, r.UltimaActividad, r.NumeroRegistros,
       COALESCE(e.Especialidad, 'MEDICINA GENERAL'), q.FechaPrimerQuirofano, q.AreaQuirofano
FROM rango r
LEFT JOIN esp e ON e.OidIngreso = r.OidIngreso
LEFT JOIN qx q ON q.OidIngreso = r.OidIngreso;
"""

_REFRESH_OCUPACION = """
DELETE FROM OcupacionDiaria;
INSERT INTO OcupacionDiaria (Fecha, Servicio, CamasTotales, CamasOcupadas, PorcentajeOcupacion)
WITH RECURSIVE dias(Fecha) AS (
    SELECT DATE(MIN(FechaIngreso)) FROM Ingresos WHERE FechaIngreso IS NOT NULL
    UNION ALL
    SELECT DATE(Fecha, '+1 day') FROM dias
    WHERE Fecha < (SELECT Fecha FROM FechaReferencia)
),
capacidad AS (
    SELECT Servicio, COUNT(*) AS CamasTotales FROM CatalogoCamas GROUP BY Servicio
),
estancias AS (
    SELECT c.Servicio, v.CodigoCama, v.FechaInicioEstancia AS Inicio, v.FechaFinEstimada AS Fin
    FROM VistaIngresos v
    JOIN CatalogoCamas c ON c.CodigoCama = v.CodigoCama
    WHERE v.Origen = 'HIS'
)
SELECT d.Fecha, cap.Servicio, cap.CamasTotales,
       COUNT(DISTINCT e.CodigoCama),
       ROUND(100.0 * COUNT(DISTINCT e.CodigoCama) / cap.CamasTotales, 1)
FROM dias d
CROSS JOIN capacidad cap
LEFT JOIN estancias e
       ON e.Servicio = cap.Servicio
      AND e.Inicio <= d.Fecha || ' 23:59:59'
      AND e.Fin >= d.Fecha || ' 00:00:00'
WHERE d.Fecha IS NOT NULL
GROUP BY d.Fecha, cap.Servicio;
"""

_CONSUMPTION_SQL = """
SELECT
    CodigoServicio AS Codigo,
    MAX(NombreServicio) AS Nombre,
    SUM(Cantidad) AS Total,
    SUM(CASE WHEN FechaPrestacion > DATE(:ref, '-30 days')
              AND FechaPrestacion <= :ref || ' 23:59:59' THEN Cantidad ELSE 0 END) AS Ultimos30,
    AVG(CASE WHEN AreaServicio LIKE '%DISPOS%' THEN 1.0 ELSE 0.0 END) AS FraccionDispositivo
FROM MedicamentoInsumo
WHERE CodigoServicio NOT IN ('No Registrado', '0')
GROUP BY CodigoServicio
"""

ATC_GROUPS = {
    "A": "Tracto alimentario y metabolismo", "B": "Sangre y órganos hematopoyéticos",
    "C": "Sistema cardiovascular", "D": "Dermatológicos",
    "G": "Genitourinario y hormonas sexuales", "H": "Hormonas sistémicas",
    "J": "Antiinfecciosos (antibióticos)", "L": "Antineoplásicos e inmunomoduladores",
    "M": "Sistema musculoesquelético", "N": "Sistema nervioso (analgésicos, sedantes)",
    "P": "Antiparasitarios", "R": "Sistema respiratorio", "S": "Órganos de los sentidos",
    "V": "Varios (oxígeno, soluciones, contrastes)",
}


# --------------------------------------------------------------------------- #
# Construcción y refresco
# --------------------------------------------------------------------------- #


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_param(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT Valor FROM ParametrosSistema WHERE Clave = ?", (key,)).fetchone()
    return row[0] if row else None


def set_param(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO ParametrosSistema (Clave, Valor, ActualizadoEn) VALUES (?, ?, ?) "
        "ON CONFLICT(Clave) DO UPDATE SET Valor = excluded.Valor, ActualizadoEn = excluded.ActualizadoEn",
        (key, value, _now()),
    )


def _his_tables_exist(conn: sqlite3.Connection) -> bool:
    found = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    return all(table in found for table in setup_db.LOAD_ORDER)


def data_signature(conn: sqlite3.Connection) -> str:
    """Huella barata de las tablas del HIS para detectar si hay que recalcular."""
    parts = []
    for table in setup_db.LOAD_ORDER:
        count, max_rowid = conn.execute(f"SELECT COUNT(*), MAX(rowid) FROM {table}").fetchone()
        parts.append(f"{table}:{count}:{max_rowid}")
    return "|".join(parts)


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO MapaServicio (NombreGrupoCama, Servicio) VALUES (?, ?)", MAPA_SERVICIO
    )
    if conn.execute("SELECT COUNT(*) FROM Medico").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO Medico (IdMedico, Nombre, Especialidad, Departamento, RegistroProfesional, "
            "Turno, Estado, Telefono, Email, Consultorio, Avatar, Origen) VALUES "
            "(:IdMedico, :Nombre, :Especialidad, :Departamento, :RegistroProfesional, :Turno, "
            ":Estado, :Telefono, :Email, :Consultorio, :Avatar, 'Demo')",
            DEMO_DOCTORS,
        )
    if conn.execute("SELECT COUNT(*) FROM Cita").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO Cita (IdCita, IdPacienteApp, NombrePaciente, IdMedico, NombreMedico, "
            "Especialidad, Fecha, Hora, Motivo, Estado, Prioridad, CreadoEn) VALUES "
            "(:IdCita, :IdPacienteApp, :NombrePaciente, :IdMedico, :NombreMedico, :Especialidad, "
            ":Fecha, :Hora, :Motivo, :Estado, :Prioridad, :CreadoEn)",
            [{**apt, "CreadoEn": _now()} for apt in DEMO_APPOINTMENTS],
        )


def _create_views(conn: sqlite3.Connection) -> None:
    for name in reversed(VIEW_NAMES):
        conn.execute(f"DROP VIEW IF EXISTS {name}")
    for _, ddl in VIEWS:
        conn.execute(ddl)


def update_reference_moment(conn: sqlite3.Connection) -> str:
    """'Hoy' para el sistema = último ingreso registrado en el HIS (o el valor fijado en .env)."""
    configured = get_settings().reference_datetime
    if configured and configured.lower() != "auto":
        moment = configured
    else:
        row = conn.execute(
            "SELECT MAX(i.FechaIngreso) FROM Ingresos i "
            "LEFT JOIN IngresoGestion g ON g.OidIngreso = i.OidIngreso "
            "WHERE COALESCE(g.Origen, 'HIS') = 'HIS'"
        ).fetchone()
        moment = row[0] or _now()
    set_param(conn, REFERENCE_KEY, moment)
    return moment


def _medication_category(code: str, device_fraction: float) -> str:
    code = (code or "").upper()
    if code.startswith("DM") or device_fraction >= 0.5:
        return "Dispositivo médico"
    atc = code[2:] if code.startswith("NP") else code
    if len(atc) >= 5 and atc[0] in ATC_GROUPS and atc[1:3].isdigit() and atc[3:5].isalpha():
        return ATC_GROUPS[atc[0]]
    if code.startswith("MAN"):
        return "Preparación magistral"
    return "Medicamento (otros)"


def _refresh_inventory(conn: sqlite3.Connection, reference_date: str) -> int:
    """
    Farmacia: el HIS solo registra dispensaciones (consumo). El stock actual,
    el lote y el vencimiento se SIMULAN de forma determinista (misma semilla =
    mismos valores) a partir del consumo real, y quedan marcados con
    StockSimulado = 1. Si un usuario actualiza el stock por la API, el registro
    pasa a StockSimulado = 0 y deja de recalcularse.
    """
    ref = date.fromisoformat(reference_date)
    existing = {
        row["CodigoMedicamento"]: row
        for row in conn.execute("SELECT CodigoMedicamento, StockSimulado FROM InventarioFarmacia")
    }
    now = _now()
    upserts = []
    for row in conn.execute(_CONSUMPTION_SQL, {"ref": reference_date}):
        code = row["Codigo"]
        seed = zlib.crc32(code.encode("utf-8"))
        daily = round((row["Ultimos30"] or 0) / 30.0, 3)
        simulated = code not in existing or existing[code]["StockSimulado"] == 1
        if daily > 0:
            coverage_days = 1 + seed % 40
            stock = math.ceil(daily * coverage_days)
            minimum = math.ceil(daily * SAFETY_STOCK_DAYS)
        else:
            stock, minimum = 5 + seed % 50, 0
        upserts.append({
            "code": code,
            "name": row["Nombre"],
            "category": _medication_category(code, row["FraccionDispositivo"] or 0.0),
            "total": row["Total"] or 0,
            "last30": row["Ultimos30"] or 0,
            "daily": daily,
            "stock": stock,
            "minimum": minimum,
            "batch": f"L-{10000 + seed % 90000}",
            "expiry": (ref + timedelta(days=30 + seed % 700)).isoformat(),
            "simulated": 1 if simulated else 0,
            "now": now,
        })

    conn.executemany(
        """
        INSERT INTO InventarioFarmacia (
            CodigoMedicamento, NombreMedicamento, Categoria, Unidad, ConsumoTotal,
            ConsumoUltimos30Dias, ConsumoDiarioPromedio, StockActual, StockMinimo,
            Lote, FechaVencimiento, StockSimulado, ActualizadoEn
        ) VALUES (:code, :name, :category, 'Unidades', :total, :last30, :daily, :stock,
                  :minimum, :batch, :expiry, 1, :now)
        ON CONFLICT(CodigoMedicamento) DO UPDATE SET
            NombreMedicamento = excluded.NombreMedicamento,
            Categoria = excluded.Categoria,
            ConsumoTotal = excluded.ConsumoTotal,
            ConsumoUltimos30Dias = excluded.ConsumoUltimos30Dias,
            ConsumoDiarioPromedio = excluded.ConsumoDiarioPromedio,
            StockActual = CASE WHEN InventarioFarmacia.StockSimulado = 1
                               THEN excluded.StockActual ELSE InventarioFarmacia.StockActual END,
            StockMinimo = CASE WHEN InventarioFarmacia.StockSimulado = 1
                               THEN excluded.StockMinimo ELSE InventarioFarmacia.StockMinimo END,
            ActualizadoEn = excluded.ActualizadoEn
        """,
        upserts,
    )
    return len(upserts)


def refresh_materialized(conn: sqlite3.Connection) -> dict[str, float]:
    """Recalcula las tablas derivadas. Se llama al arrancar y tras cada carga de archivos."""
    timings: dict[str, float] = {}

    start = time.perf_counter()
    moment = update_reference_moment(conn)
    conn.executescript(_REFRESH_ACTIVIDAD)
    timings["actividad_ingreso_s"] = round(time.perf_counter() - start, 2)

    start = time.perf_counter()
    conn.executescript(_REFRESH_OCUPACION)
    timings["ocupacion_diaria_s"] = round(time.perf_counter() - start, 2)

    start = time.perf_counter()
    items = _refresh_inventory(conn, moment[:10])
    timings["inventario_s"] = round(time.perf_counter() - start, 2)
    timings["inventario_items"] = items

    set_param(conn, SIGNATURE_KEY, data_signature(conn))
    set_param(conn, REFRESHED_AT_KEY, _now())
    conn.commit()
    logger.info("Capa semántica recalculada: %s", timings)
    return timings


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    """Migración mínima: agrega la columna si una versión anterior de la tabla no la tenía."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def apply_privacy_migrations(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Privacidad por diseño sobre datos YA existentes (idempotente):
    - todo nombre de paciente se reemplaza por su seudónimo Paciente_<IdPaciente>,
    - todo documento en claro se reemplaza por su HMAC y se borra,
    - las citas y los estados manuales de cama no conservan nombres.
    """
    from backend.core.privacy import hash_document  # import local: evita ciclo de configuración

    _ensure_column(conn, "IngresoGestion", "DocumentoHash", "TEXT")
    stats = {}
    stats["pacientes_seudonimizados"] = conn.execute(
        "UPDATE Paciente SET NombrePaciente = 'Paciente_' || IdPaciente "
        "WHERE NombrePaciente IS NULL OR NombrePaciente <> 'Paciente_' || IdPaciente"
    ).rowcount
    clear_documents = conn.execute(
        "SELECT OidIngreso, DocumentoIdentidad FROM IngresoGestion "
        "WHERE DocumentoIdentidad IS NOT NULL AND DocumentoIdentidad <> ''"
    ).fetchall()
    for oid, document in clear_documents:
        conn.execute(
            "UPDATE IngresoGestion SET DocumentoHash = ?, DocumentoIdentidad = NULL WHERE OidIngreso = ?",
            (hash_document(document), oid),
        )
    stats["documentos_cifrados"] = len(clear_documents)
    stats["citas_seudonimizadas"] = conn.execute(
        "UPDATE Cita SET NombrePaciente = 'Paciente ' || COALESCE(IdPacienteApp, IdCita) "
        "WHERE NombrePaciente IS NULL OR NombrePaciente <> 'Paciente ' || COALESCE(IdPacienteApp, IdCita)"
    ).rowcount
    stats["telefonos_eliminados"] = conn.execute(
        "UPDATE IngresoGestion SET Telefono = NULL WHERE Telefono IS NOT NULL"
    ).rowcount
    stats["camas_sin_nombre"] = conn.execute(
        "UPDATE CamaEstadoManual SET NombrePacienteApp = NULL WHERE NombrePacienteApp IS NOT NULL"
    ).rowcount
    if any(stats.values()):
        logger.info("Migración de privacidad aplicada: %s", stats)
    return stats


def ensure_semantic_layer(conn: sqlite3.Connection, force_refresh: bool = False) -> dict:
    """
    Idempotente. Garantiza que existan el esquema del HIS (vacío si no se ha
    corrido setup_db.py), las tablas operativas, las vistas y los datos
    derivados al día.
    """
    if not _his_tables_exist(conn):
        logger.warning("No existen las tablas del HIS: se crea el esquema vacío (ejecute setup_db.py).")
        conn.executescript(setup_db.SCHEMA_SQL)

    conn.executescript(OPERATIONAL_DDL)
    conn.executescript(HIS_INDEXES)
    _seed(conn)
    apply_privacy_migrations(conn)
    if get_param(conn, REFERENCE_KEY) is None:
        update_reference_moment(conn)
    _create_views(conn)
    conn.commit()

    signature = data_signature(conn)
    stale = get_param(conn, SIGNATURE_KEY) != signature
    if force_refresh or stale:
        return {"refreshed": True, **refresh_materialized(conn)}
    return {"refreshed": False}
