"""KPIs agregados del dashboard (/stats)."""
from __future__ import annotations

import sqlite3

from backend.schemas.resources import Stats

_STATS_SQL = """
SELECT
    (SELECT COUNT(*) FROM VistaIngresos WHERE Activo = 1) AS active_patients,
    (SELECT COUNT(*) FROM VistaIngresos
      WHERE Activo = 1 AND (Estado = 'Crítico' OR NivelTriage = 1)) AS critical_patients,
    (SELECT COUNT(*) FROM EstadoCamas) AS total_beds,
    (SELECT COUNT(*) FROM EstadoCamas WHERE Estado = 'Ocupada') AS occupied_beds,
    (SELECT COUNT(*) FROM EstadoCamas WHERE Estado = 'Libre') AS free_beds,
    (SELECT COUNT(*) FROM EstadoCamas WHERE Estado NOT IN ('Ocupada', 'Libre')) AS maintenance_beds,
    (SELECT COUNT(*) FROM Cita WHERE Fecha = DATE('now', 'localtime')) AS today_appointments,
    (SELECT COUNT(*) FROM Medico WHERE Estado = 'Disponible') AS available_doctors,
    (SELECT COUNT(*) FROM InventarioFarmacia WHERE Estado = 'Crítico') AS critical_meds,
    (SELECT COUNT(*) FROM InventarioFarmacia WHERE Estado = 'Bajo') AS low_stock_meds,
    (SELECT Fecha FROM FechaReferencia) AS reference_date,
    (SELECT ROUND(AVG(MinutosEspera), 1) FROM EsperaUrgencias
      WHERE Fecha > DATE((SELECT Fecha FROM FechaReferencia), '-7 days')
        AND Fecha <= (SELECT Fecha FROM FechaReferencia)) AS avg_wait_minutes_last_7_days,
    (SELECT COUNT(*) FROM Ingresos
      WHERE DATE(FechaIngreso) = (SELECT Fecha FROM FechaReferencia)) AS admissions_on_reference_date
"""


def get_stats(conn: sqlite3.Connection) -> Stats:
    row = dict(conn.execute(_STATS_SQL).fetchone())
    total = row["total_beds"] or 0
    row["occupancy_rate"] = round(100 * row["occupied_beds"] / total) if total else 0
    return Stats(**row)
