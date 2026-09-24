"""
Dashboard ejecutivo (GET /api/dashboard): todos los datos del tablero BI en una sola llamada.

Filtros:
- period: today | 7d | 30d  (relativo a la fecha de referencia del sistema)
- service: 'all' o un servicio (ej. 'Cuidados Intensivos (UCI)')

Privacidad: ningún bloque devuelve nombres ni documentos; los pacientes se
identifican con su número de ingreso y un seudónimo.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from backend.core.errors import ValidationError
from backend.core.privacy import patient_pseudonym
from backend.core.timeutils import to_minutes_precision
from backend.db.semantic_layer import REFRESHED_AT_KEY, get_param

PERIOD_DAYS = {"today": 1, "7d": 7, "30d": 30}
PERIOD_LABELS = {"today": "Hoy", "7d": "Últimos 7 días", "30d": "Último mes"}
ALL_SERVICES = "all"


def _window(reference: str, days: int) -> tuple[str, str]:
    end = date.fromisoformat(reference)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _service_clause(service: str, column: str) -> tuple[str, list]:
    if service == ALL_SERVICES:
        return "", []
    return f" AND {column} = ?", [service]


def list_services(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT Servicio FROM CatalogoCamas ORDER BY Servicio")]


def _kpis(conn, start, end, service) -> dict:
    svc_beds, p_beds = _service_clause(service, "Servicio")
    beds = conn.execute(
        "SELECT COUNT(*) AS total, SUM(Estado = 'Ocupada') AS ocupadas, SUM(Estado = 'Libre') AS libres "
        f"FROM EstadoCamas WHERE 1 = 1{svc_beds}", p_beds,
    ).fetchone()
    total, occupied = beds["total"] or 0, beds["ocupadas"] or 0

    svc_wait, p_wait = _service_clause(service, "Servicio")
    wait = conn.execute(
        "SELECT ROUND(AVG(MinutosEspera), 1) AS promedio, COUNT(*) AS pacientes FROM EsperaUrgencias "
        f"WHERE Fecha BETWEEN ? AND ?{svc_wait}", [start, end, *p_wait],
    ).fetchone()

    svc_qx, p_qx = _service_clause(service, "cp.Servicio")
    surgery = conn.execute(
        "SELECT COUNT(*) AS programadas, SUM(cp.EstadoCirugia = 'Realizada') AS realizadas "
        "FROM CirugiasProgramadas cp LEFT JOIN Ingresos i ON i.OidIngreso = cp.OidIngreso "
        "WHERE cp.EstadoCirugia <> 'Sin ingreso en el periodo' "
        f"AND COALESCE(cp.Fecha, DATE(i.FechaIngreso)) BETWEEN ? AND ?{svc_qx}", [start, end, *p_qx],
    ).fetchone()
    scheduled, performed = surgery["programadas"] or 0, surgery["realizadas"] or 0

    meds = conn.execute(
        "SELECT SUM(Estado = 'Crítico') AS criticos, SUM(Estado = 'Bajo') AS bajos, "
        "SUM(DiasInventario < 5) AS menos_5_dias FROM InventarioFarmacia"
    ).fetchone()

    svc_pat, p_pat = _service_clause(service, "Servicio")
    patients = conn.execute(
        "SELECT SUM(Activo = 1) AS activos, SUM(Activo = 1 AND (Estado = 'Crítico' OR NivelTriage = 1)) AS criticos, "
        "SUM(DATE(FechaIngreso) BETWEEN ? AND ?) AS ingresos "
        f"FROM VistaIngresos WHERE 1 = 1{svc_pat}", [start, end, *p_pat],
    ).fetchone()

    return {
        "totalBeds": total,
        "occupiedBeds": occupied,
        "freeBeds": beds["libres"] or 0,
        "occupancyRate": round(100 * occupied / total, 1) if total else 0,
        "avgWaitMinutes": wait["promedio"],
        "waitPatients": wait["pacientes"] or 0,
        "surgeriesScheduled": scheduled,
        "surgeriesPerformed": performed,
        "surgeryComplianceRate": round(100 * performed / scheduled, 1) if scheduled else None,
        "criticalMeds": meds["criticos"] or 0,
        "lowStockMeds": meds["bajos"] or 0,
        "medsUnder5Days": meds["menos_5_dias"] or 0,
        "activePatients": patients["activos"] or 0,
        "criticalPatients": patients["criticos"] or 0,
        "admissions": patients["ingresos"] or 0,
    }


def _occupancy_trend(conn, reference, days, service) -> dict:
    trend_days = max(days, 7)
    start, end = _window(reference, trend_days)
    svc, params = _service_clause(service, "Servicio")
    occupancy = {
        r["Fecha"]: r["pct"]
        for r in conn.execute(
            "SELECT Fecha, ROUND(100.0 * SUM(CamasOcupadas) / SUM(CamasTotales), 1) AS pct "
            f"FROM OcupacionDiaria WHERE Fecha BETWEEN ? AND ?{svc} GROUP BY Fecha",
            [start, end, *params],
        )
    }
    admissions = {
        r["Fecha"]: r["n"]
        for r in conn.execute(
            "SELECT DATE(FechaIngreso) AS Fecha, COUNT(*) AS n FROM VistaIngresos "
            f"WHERE DATE(FechaIngreso) BETWEEN ? AND ?{svc} GROUP BY 1",
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


def _service_distribution(conn, start, end) -> dict:
    rows = conn.execute(
        "SELECT Servicio, COUNT(*) AS n FROM VistaIngresos "
        "WHERE DATE(FechaIngreso) BETWEEN ? AND ? GROUP BY Servicio ORDER BY n DESC",
        [start, end],
    ).fetchall()
    return {"labels": [r["Servicio"] for r in rows], "values": [r["n"] for r in rows]}


def _wards(conn, service) -> list[dict]:
    # Todos los servicios -> una barra por servicio; un servicio -> detalle por subgrupo (drill-down)
    group_col = "Servicio" if service == ALL_SERVICES else "SubgrupoCama"
    svc, params = _service_clause(service, "Servicio")
    rows = conn.execute(
        f"SELECT {group_col} AS grupo, COUNT(*) AS total, SUM(Estado = 'Ocupada') AS ocupadas, "
        "SUM(Estado = 'Libre') AS libres "
        f"FROM EstadoCamas WHERE 1 = 1{svc} GROUP BY {group_col} ORDER BY total DESC",
        params,
    ).fetchall()
    return [
        {
            "wing": r["grupo"],
            "total": r["total"],
            "occupied": r["ocupadas"] or 0,
            "free": r["libres"] or 0,
            "unavailable": r["total"] - (r["ocupadas"] or 0) - (r["libres"] or 0),
            "occupancyPct": round(100 * (r["ocupadas"] or 0) / r["total"]) if r["total"] else 0,
        }
        for r in rows
    ]


def _urgent_patients(conn, service, limit: int = 12) -> list[dict]:
    svc, params = _service_clause(service, "Servicio")
    rows = conn.execute(
        "SELECT OidIngreso, IdPaciente, NivelTriage, NombreDiagnostico, CodigoCama, CamaVirtual, "
        "Servicio, FechaIngreso, Estado FROM VistaIngresos "
        f"WHERE Activo = 1{svc} "
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


def _critical_meds(conn, limit: int = 8) -> list[dict]:
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
    if period not in PERIOD_DAYS:
        raise ValidationError(f"Periodo inválido: {period}", {"allowed": list(PERIOD_DAYS)})
    services = list_services(conn)
    if service != ALL_SERVICES and service not in services:
        raise ValidationError(f"Servicio desconocido: {service}", {"allowed": services})

    reference = conn.execute("SELECT Fecha FROM FechaReferencia").fetchone()
    reference_date = reference[0] if reference and reference[0] else date.today().isoformat()
    days = PERIOD_DAYS[period]
    start, end = _window(reference_date, days)

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
