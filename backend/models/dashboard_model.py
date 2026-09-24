"""
Modelo del dashboard ejecutivo (capa Modelo): datos de GET /api/dashboard.

Por qué una sola llamada: el tablero BI se refresca cada minuto; agrupar KPIs,
tendencias, distribución, capacidad, censo y stock crítico en una respuesta evita
7 peticiones y garantiza que todos los bloques usen el mismo periodo y servicio.

Filtros:
- period: today | 7d | 30d  (relativo a la fecha de referencia del sistema)
- service: 'all' o un servicio (ej. 'Cuidados Intensivos (UCI)')

Privacidad: ningún bloque devuelve nombres ni documentos; los pacientes se
identifican con su número de ingreso y un seudónimo.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from backend.core.errors import BadRequestError
from backend.core.privacy import patient_pseudonym
from backend.core.time_utils import to_minutes_precision
from backend.models.semantic_layer import REFRESHED_AT_KEY, get_param

PERIOD_DAYS = {"today": 1, "7d": 7, "30d": 30}
PERIOD_LABELS = {"today": "Hoy", "7d": "Últimos 7 días", "30d": "Último mes"}
ALL_SERVICES = "all"
URGENT_PATIENTS_LIMIT = 12
CRITICAL_MEDS_LIMIT = 8


def _date_window(reference: str, days: int) -> tuple[str, str]:
    """Ventana [inicio, fin] de `days` días que termina en la fecha de referencia (inclusive)."""
    end = date.fromisoformat(reference)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _service_clause(service: str, column: str) -> tuple[str, list]:
    """Fragmento WHERE parametrizado para filtrar por servicio ('all' = sin filtro)."""
    if service == ALL_SERVICES:
        return "", []
    return f" AND {column} = ?", [service]


def list_services(conn: sqlite3.Connection) -> list[str]:
    """Servicios con camas físicas (opciones del filtro del dashboard)."""
    return [r[0] for r in conn.execute("SELECT DISTINCT Servicio FROM CatalogoCamas ORDER BY Servicio")]


def _kpis(conn: sqlite3.Connection, start: str, end: str, service: str) -> dict:
    """Tarjetas de KPIs: camas, espera en urgencias, cirugías, farmacia y pacientes."""
    service_filter, service_params = _service_clause(service, "Servicio")
    beds = conn.execute(
        "SELECT COUNT(*) AS total, SUM(Estado = 'Ocupada') AS occupied, SUM(Estado = 'Libre') AS free "
        f"FROM EstadoCamas WHERE 1 = 1{service_filter}", service_params,
    ).fetchone()
    total, occupied = beds["total"] or 0, beds["occupied"] or 0

    wait = conn.execute(
        "SELECT ROUND(AVG(MinutosEspera), 1) AS avg_minutes, COUNT(*) AS patients FROM EsperaUrgencias "
        f"WHERE Fecha BETWEEN ? AND ?{service_filter}", [start, end, *service_params],
    ).fetchone()

    surgery_filter, surgery_params = _service_clause(service, "cp.Servicio")
    surgery = conn.execute(
        "SELECT COUNT(*) AS scheduled, SUM(cp.EstadoCirugia = 'Realizada') AS performed "
        "FROM CirugiasProgramadas cp LEFT JOIN Ingresos i ON i.OidIngreso = cp.OidIngreso "
        "WHERE cp.EstadoCirugia <> 'Sin ingreso en el periodo' "
        # Las cirugías no realizadas no tienen fecha: se ubican en el periodo por su fecha de ingreso
        f"AND COALESCE(cp.Fecha, DATE(i.FechaIngreso)) BETWEEN ? AND ?{surgery_filter}",
        [start, end, *surgery_params],
    ).fetchone()
    scheduled, performed = surgery["scheduled"] or 0, surgery["performed"] or 0

    meds = conn.execute(
        "SELECT SUM(Estado = 'Crítico') AS critical, SUM(Estado = 'Bajo') AS low, "
        "SUM(DiasInventario < 5) AS under_5_days FROM InventarioFarmacia"
    ).fetchone()

    patients = conn.execute(
        "SELECT SUM(Activo = 1) AS active, "
        "SUM(Activo = 1 AND (Estado = 'Crítico' OR NivelTriage = 1)) AS critical, "
        "SUM(DATE(FechaIngreso) BETWEEN ? AND ?) AS admissions "
        f"FROM VistaIngresos WHERE 1 = 1{service_filter}", [start, end, *service_params],
    ).fetchone()

    return {
        "totalBeds": total,
        "occupiedBeds": occupied,
        "freeBeds": beds["free"] or 0,
        "occupancyRate": round(100 * occupied / total, 1) if total else 0,
        "avgWaitMinutes": wait["avg_minutes"],
        "waitPatients": wait["patients"] or 0,
        "surgeriesScheduled": scheduled,
        "surgeriesPerformed": performed,
        "surgeryComplianceRate": round(100 * performed / scheduled, 1) if scheduled else None,
        "criticalMeds": meds["critical"] or 0,
        "lowStockMeds": meds["low"] or 0,
        "medsUnder5Days": meds["under_5_days"] or 0,
        "activePatients": patients["active"] or 0,
        "criticalPatients": patients["critical"] or 0,
        "admissions": patients["admissions"] or 0,
    }


def _occupancy_trend(conn: sqlite3.Connection, reference: str, days: int, service: str) -> dict:
    """Serie diaria de % de ocupación e ingresos (mínimo 7 días para que la gráfica tenga forma)."""
    trend_days = max(days, 7)
    start, end = _date_window(reference, trend_days)
    service_filter, params = _service_clause(service, "Servicio")
    occupancy = {
        row["day"]: row["occupancy_pct"]
        for row in conn.execute(
            "SELECT Fecha AS day, ROUND(100.0 * SUM(CamasOcupadas) / SUM(CamasTotales), 1) AS occupancy_pct "
            f"FROM OcupacionDiaria WHERE Fecha BETWEEN ? AND ?{service_filter} GROUP BY Fecha",
            [start, end, *params],
        )
    }
    admissions = {
        row["day"]: row["admissions"]
        for row in conn.execute(
            "SELECT DATE(FechaIngreso) AS day, COUNT(*) AS admissions FROM VistaIngresos "
            f"WHERE DATE(FechaIngreso) BETWEEN ? AND ?{service_filter} GROUP BY 1",
            [start, end, *params],
        )
    }
    dates = [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(trend_days)]
    return {
        "dates": dates,
        "labels": [f"{d[8:10]}/{d[5:7]}" for d in dates],
        "occupancyPct": [occupancy.get(d, 0) for d in dates],
        "admissions": [admissions.get(d, 0) for d in dates],
        "windowDays": trend_days,
    }


def _service_distribution(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Ingresos del periodo por servicio (gráfica de distribución)."""
    rows = conn.execute(
        "SELECT Servicio, COUNT(*) AS admissions FROM VistaIngresos "
        "WHERE DATE(FechaIngreso) BETWEEN ? AND ? GROUP BY Servicio ORDER BY admissions DESC",
        [start, end],
    ).fetchall()
    return {"labels": [r["Servicio"] for r in rows], "values": [r["admissions"] for r in rows]}


def _wards(conn: sqlite3.Connection, service: str) -> list[dict]:
    """Capacidad por área: todos los servicios -> una barra por servicio; uno -> detalle por subgrupo."""
    group_column = "Servicio" if service == ALL_SERVICES else "SubgrupoCama"
    service_filter, params = _service_clause(service, "Servicio")
    rows = conn.execute(
        f"SELECT {group_column} AS ward, COUNT(*) AS total, SUM(Estado = 'Ocupada') AS occupied, "
        "SUM(Estado = 'Libre') AS free "
        f"FROM EstadoCamas WHERE 1 = 1{service_filter} GROUP BY {group_column} ORDER BY total DESC",
        params,
    ).fetchall()
    wards = []
    for row in rows:
        occupied, free = row["occupied"] or 0, row["free"] or 0
        wards.append({
            "wing": row["ward"],
            "total": row["total"],
            "occupied": occupied,
            "free": free,
            "unavailable": row["total"] - occupied - free,   # desinfección / mantenimiento
            "occupancyPct": round(100 * occupied / row["total"]) if row["total"] else 0,
        })
    return wards


def _urgent_patients(conn: sqlite3.Connection, service: str, limit: int = URGENT_PATIENTS_LIMIT) -> list[dict]:
    """Censo priorizado: pacientes activos ordenados por nivel de triage (1 = más urgente)."""
    service_filter, params = _service_clause(service, "Servicio")
    rows = conn.execute(
        "SELECT OidIngreso, IdPaciente, NivelTriage, NombreDiagnostico, CodigoCama, CamaVirtual, "
        "Servicio, FechaIngreso, Estado FROM VistaIngresos "
        f"WHERE Activo = 1{service_filter} "
        "ORDER BY COALESCE(NivelTriage, 9), FechaIngreso DESC LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [
        {
            "id": f"ING-{r['OidIngreso']}",
            "name": patient_pseudonym(r["IdPaciente"]),
            "triageLevel": r["NivelTriage"],
            "diagnosis": r["NombreDiagnostico"],
            "roomNumber": f"Cama {r['CodigoCama']}" if not r["CamaVirtual"] else "Cama virtual",
            "department": r["Servicio"],
            "admissionDate": to_minutes_precision(r["FechaIngreso"]),
            "status": r["Estado"],
        }
        for r in rows
    ]


def _critical_meds(conn: sqlite3.Connection, limit: int = CRITICAL_MEDS_LIMIT) -> list[dict]:
    """Medicamentos en estado Crítico o Bajo, los de menor cobertura primero."""
    rows = conn.execute(
        "SELECT CodigoMedicamento, NombreMedicamento, StockActual, StockMinimo, DiasInventario, "
        "ConsumoDiarioPromedio, Estado FROM InventarioFarmacia "
        "WHERE Estado IN ('Crítico', 'Bajo') ORDER BY DiasInventario IS NULL, DiasInventario, "
        "ConsumoDiarioPromedio DESC LIMIT ?",
        [limit],
    ).fetchall()
    return [
        {
            "id": r["CodigoMedicamento"], "name": r["NombreMedicamento"], "stock": r["StockActual"],
            "minStock": r["StockMinimo"], "daysOfInventory": r["DiasInventario"],
            "dailyConsumption": r["ConsumoDiarioPromedio"], "status": r["Estado"],
        }
        for r in rows
    ]


def get_dashboard(conn: sqlite3.Connection, period: str = "today", service: str = ALL_SERVICES) -> dict:
    """
    Arma el tablero completo. Los periodos son relativos a la fecha de referencia
    (último dato del HIS) y no a la fecha del servidor, porque el extracto es histórico.
    """
    if period not in PERIOD_DAYS:
        raise BadRequestError(f"Periodo inválido: {period}", {"allowed": list(PERIOD_DAYS)})
    services = list_services(conn)
    if service != ALL_SERVICES and service not in services:
        raise BadRequestError(f"Servicio desconocido: {service}", {"allowed": services})

    reference = conn.execute("SELECT Fecha FROM FechaReferencia").fetchone()
    reference_date = reference[0] if reference and reference[0] else date.today().isoformat()
    days = PERIOD_DAYS[period]
    start, end = _date_window(reference_date, days)

    return {
        "source": "api",
        "referenceDate": reference_date,
        "period": period,
        "periodLabel": PERIOD_LABELS[period],
        "periodStart": start,
        "periodEnd": end,
        "service": service,
        "services": services,
        "lastSync": get_param(conn, REFRESHED_AT_KEY),
        "kpis": _kpis(conn, start, end, service),
        "occupancyTrend": _occupancy_trend(conn, reference_date, days, service),
        "serviceDistribution": _service_distribution(conn, start, end),
        "wards": _wards(conn, service),
        "urgentPatients": _urgent_patients(conn, service),
        "criticalMeds": _critical_meds(conn),
    }
