"""
Valor añadido del reto: alertas predictivas, recomendaciones y análisis de causa raíz.

Todo se calcula con reglas y estadística simple sobre las vistas semánticas, SIN LLM:
cada cifra es verificable y el módulo funciona aunque no haya IA disponible.

- wait_time_drivers(): por qué cambió la espera en urgencias (descomposición mezcla/desempeño).
- demand_alerts(): picos de ingresos por familia clínica y medicamentos a reforzar.
- operational_alerts(): punto 7 del reto -> desabastecimiento, abrir camas, reasignar personal
  y optimizar la programación de quirófanos.
- build_briefing(): resumen proactivo que junta todo lo anterior.

Ventanas de análisis (relativas a la fecha de referencia, el "hoy" del HIS):
  semana actual = los 7 días que terminan en `end`;
  referencia    = las 4 semanas anteriores (28 días).
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from backend.core.errors import BadRequestError

WINDOW_DAYS = 7
BASELINE_WEEKS = 4
BASKET_WEEKS = 8                 # historia usada para aprender la canasta diagnóstico -> medicamento

# Causa raíz de la espera
MIN_WAIT_DELTA_MINUTES = 3.0     # cambios menores no se reportan como aumento/disminución
WAIT_Z_THRESHOLD = 1.96          # significancia bilateral al 95 %

# Alertas de demanda
DEMAND_Z_THRESHOLD = 1.645       # prueba de Poisson unilateral al 95 % (solo interesan aumentos)
MIN_WEEKLY_BASELINE = 8          # familias con menos ingresos/semana son demasiado ruidosas
MIN_GROWTH = 0.10                # la proyección debe superar la referencia en al menos 10 %
MAX_DEMAND_ALERTS = 3
BASKET_SIZE = 3
BASKET_MIN_SHARE = 0.10          # el medicamento lo usa al menos el 10 % de los ingresos de la familia
BASKET_MIN_LIFT = 1.5            # y es 1,5 veces más frecuente que en el resto del hospital
EXCLUDED_BASKET_CATEGORIES = ("Dispositivo médico", "Varios (oxígeno, soluciones, contrastes)")
SECONDARY_DRIVER_MIN_PCT = 25.0  # un segundo factor se menciona si explica al menos el 25 % del cambio
MED_NAME_MAX_CHARS = 48

# Alertas operativas
TARGET_COVERAGE_DAYS = 14        # las cantidades a pedir apuntan a 14 días de cobertura
LOW_INVENTORY_DAYS = 5
HIGH_OCCUPANCY_PCT = 85.0      # ocupación promedio de 7 días a partir de la cual se recomienda abrir camas
LOW_OCCUPANCY_PCT = 60.0       # servicios que pueden prestar personal de apoyo
MIN_SERVICE_BEDS = 5
TOP_MEDS = 5
STAFF_MIN_WAIT_GAP_MINUTES = 10.0   # diferencia de espera entre turnos que justifica reasignar personal
STAFF_MIN_WAIT_GAP_PCT = 0.20
SURGERY_WINDOW_DAYS = 28
SURGERY_IMBALANCE_PCT = 0.20        # diferencia entre el día hábil más y menos cargado (sobre el promedio)
SURGERY_CANCELLATION_PCT = 5.0
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

SEVERITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
SHIFT_HOURS = {"Mañana": "07:00-13:00", "Tarde": "13:00-19:00", "Noche": "19:00-07:00"}

# Capítulos CIE-10 (primera letra del código) agrupados en familias clínicas
CLINICAL_FAMILIES = {
    "A": "Enfermedades infecciosas", "B": "Enfermedades infecciosas",
    "C": "Neoplasias", "D": "Neoplasias y enfermedades de la sangre",
    "E": "Enfermedades endocrinas y metabólicas", "F": "Trastornos mentales",
    "G": "Enfermedades del sistema nervioso", "H": "Enfermedades del ojo y del oído",
    "I": "Enfermedades circulatorias", "J": "Enfermedades respiratorias",
    "K": "Enfermedades digestivas", "L": "Enfermedades de la piel",
    "M": "Enfermedades osteomusculares", "N": "Enfermedades genitourinarias",
    "O": "Embarazo, parto y puerperio", "P": "Afecciones perinatales",
    "Q": "Malformaciones congénitas", "R": "Síntomas no clasificados",
    "S": "Traumatismos", "T": "Traumatismos",
    "V": "Causas externas", "W": "Causas externas", "X": "Causas externas", "Y": "Causas externas",
    "Z": "Factores que influyen en la salud",
}
# Familias inespecíficas: no sirven para anticipar demanda clínica ni insumos
NON_CLINICAL_FAMILIES = frozenset({"Síntomas no clasificados", "Factores que influyen en la salud", "Causas externas"})


# --------------------------------------------------------------------------- #
# Fechas
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Windows:
    reference: str
    current_start: str
    current_end: str
    baseline_start: str
    baseline_end: str


def reference_date(conn: sqlite3.Connection) -> str:
    """Fecha del último dato del HIS (el "hoy" del sistema)."""
    row = conn.execute("SELECT Fecha FROM FechaReferencia").fetchone()
    return row[0] if row and row[0] else date.today().isoformat()


def build_windows(conn: sqlite3.Connection, end: str | None = None) -> Windows:
    """Semana actual (7 días hasta `end`) y referencia (las 4 semanas anteriores)."""
    reference = reference_date(conn)
    try:
        end_day = date.fromisoformat(end) if end else date.fromisoformat(reference)
    except ValueError as exc:
        raise BadRequestError("Fecha inválida: use el formato AAAA-MM-DD", {"end": end}) from exc
    current_start = end_day - timedelta(days=WINDOW_DAYS - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=WINDOW_DAYS * BASELINE_WEEKS - 1)
    return Windows(reference, current_start.isoformat(), end_day.isoformat(),
                   baseline_start.isoformat(), baseline_end.isoformat())


def _fmt_date(value: str) -> str:
    """'2026-09-21' -> '21/09/2026'."""
    return f"{value[8:10]}/{value[5:7]}/{value[:4]}"


def _sentence(text: str) -> str:
    """Primera letra en mayúscula y punto final, sin alterar nombres propios del resto del texto."""
    text = text.strip()
    return (text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")) if text else text


def _med_name(name: str) -> str:
    """Nombre legible y corto: 'OMEPRAZOL 40 mg  POLVO ...' -> 'Omeprazol 40 mg polvo ...'."""
    text = " ".join((name or "").split()).capitalize()
    if len(text) <= MED_NAME_MAX_CHARS:
        return text
    return text[:MED_NAME_MAX_CHARS].rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------------------- #
# Causa raíz de la espera en urgencias
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Segment:
    """Estadísticos de espera de un segmento (nivel de triage x turno) en un periodo."""
    n: int
    mean: float
    mean_sq: float


def _triage_label(level: int) -> str:
    return f"triage {level}" if level else "sin triage"


def decompose_change(base: dict[tuple, Segment], current: dict[tuple, Segment]) -> list[dict]:
    """
    Descomposición de Kitagawa del cambio en la espera promedio.

    Para cada segmento i, con participación s (fracción de pacientes) y espera media m:
        mezcla     = (s_act - s_ref) * (m_act + m_ref) / 2   -> "llegaron más pacientes de este tipo"
        desempeño  = (m_act - m_ref) * (s_act + s_ref) / 2   -> "este tipo de paciente esperó más"
    La suma de ambos efectos en todos los segmentos es EXACTAMENTE el cambio del promedio global.
    """
    n_base = sum(s.n for s in base.values()) or 1
    n_current = sum(s.n for s in current.values()) or 1
    rows = []
    for key in sorted(set(base) | set(current)):
        b, c = base.get(key), current.get(key)
        share_b = b.n / n_base if b else 0.0
        share_c = c.n / n_current if c else 0.0
        # Si el segmento no existe en un periodo, se usa la media del otro (sin efecto desempeño)
        mean_b = b.mean if b else c.mean
        mean_c = c.mean if c else b.mean
        mix = (share_c - share_b) * (mean_c + mean_b) / 2
        performance = (mean_c - mean_b) * (share_c + share_b) / 2
        rows.append({
            "key": key, "baselineShare": share_b, "currentShare": share_c,
            "baselineAvg": mean_b, "currentAvg": mean_c,
            "mixEffect": mix, "performanceEffect": performance, "contribution": mix + performance,
        })
    return rows


def _overall(segments: dict[tuple, Segment]) -> tuple[int, float, float]:
    """(pacientes, media, varianza) del periodo a partir de sus segmentos."""
    n = sum(s.n for s in segments.values())
    if not n:
        return 0, 0.0, 0.0
    mean = sum(s.n * s.mean for s in segments.values()) / n
    mean_sq = sum(s.n * s.mean_sq for s in segments.values()) / n
    return n, mean, max(0.0, mean_sq - mean * mean)


def _wait_segments(conn: sqlite3.Connection, start: str, end: str) -> dict[tuple, Segment]:
    rows = conn.execute(
        "SELECT COALESCE(NivelTriage, 0) AS triage, COALESCE(Turno, 'Sin turno') AS shift, "
        "COUNT(*) AS n, AVG(MinutosEspera) AS mean, AVG(MinutosEspera * MinutosEspera) AS mean_sq "
        "FROM EsperaUrgencias WHERE MinutosEspera IS NOT NULL AND Fecha BETWEEN ? AND ? "
        "GROUP BY triage, shift",
        [start, end],
    ).fetchall()
    return {(r["triage"], r["shift"]): Segment(r["n"], r["mean"], r["mean_sq"]) for r in rows}


def _shift_load(base: dict[tuple, Segment], current: dict[tuple, Segment]) -> list[dict]:
    """Pacientes por día en cada turno: semana actual vs. referencia."""
    def avg_wait(segments: dict[tuple, Segment], shift: str) -> float | None:
        picked = [s for (_, sh), s in segments.items() if sh == shift]
        n = sum(s.n for s in picked)
        return round(sum(s.n * s.mean for s in picked) / n, 1) if n else None

    load = []
    for shift in SHIFT_HOURS:
        per_day_c = sum(s.n for (_, sh), s in current.items() if sh == shift) / WINDOW_DAYS
        per_day_b = sum(s.n for (_, sh), s in base.items() if sh == shift) / (WINDOW_DAYS * BASELINE_WEEKS)
        load.append({
            "shift": shift, "hours": SHIFT_HOURS[shift],
            "currentPerDay": round(per_day_c, 1), "baselinePerDay": round(per_day_b, 1),
            "changePct": round(100 * (per_day_c - per_day_b) / per_day_b, 1) if per_day_b else None,
            "currentAvgWait": avg_wait(current, shift), "baselineAvgWait": avg_wait(base, shift),
        })
    return load


def _driver_sentence(driver: dict) -> tuple[str, str]:
    """(explicación, recomendación) del factor principal."""
    level, shift = driver["key"]
    who = f"pacientes {_triage_label(level)} del turno {shift.lower()}"
    hours = SHIFT_HOURS.get(shift, "")
    if driver["type"] == "desempeño":
        reason = (f"los {who} esperaron {driver['currentAvg']:.0f} min frente a "
                  f"{driver['baselineAvg']:.0f} min habituales")
        action = (f"Reforzar la atención de {_triage_label(level)} en el turno {shift.lower()} ({hours}): "
                  "revisar dotación de personal y flujo de consultorios en esa franja.")
    else:
        more = "más" if driver["currentShare"] >= driver["baselineShare"] else "menos"
        reason = (f"llegaron {more} {who} ({driver['currentShare']:.0%} de los pacientes frente a "
                  f"{driver['baselineShare']:.0%} habitual)")
        action = (f"Ajustar la dotación del turno {shift.lower()} ({hours}) al aumento de "
                  f"pacientes {_triage_label(level)}.")
    return reason, action


def wait_time_drivers(conn: sqlite3.Connection, end: str | None = None) -> dict:
    """Explica el cambio de la espera promedio en urgencias: semana actual vs. 4 semanas previas."""
    w = build_windows(conn, end)
    base = _wait_segments(conn, w.baseline_start, w.baseline_end)
    current = _wait_segments(conn, w.current_start, w.current_end)
    n_b, mean_b, var_b = _overall(base)
    n_c, mean_c, var_c = _overall(current)
    delta = mean_c - mean_b

    result = {
        "referenceDate": w.reference, "periodStart": w.current_start, "periodEnd": w.current_end,
        "baselineStart": w.baseline_start, "baselineEnd": w.baseline_end,
        "patients": {"current": n_c, "baseline": n_b},
        "currentAvgMinutes": round(mean_c, 1), "baselineAvgMinutes": round(mean_b, 1),
        "deltaMinutes": round(delta, 1), "zScore": None, "significant": False, "direction": "estable",
        "drivers": [], "shiftLoad": _shift_load(base, current), "summary": "", "recommendation": None,
    }
    if not n_b or not n_c:
        result["summary"] = "No hay suficientes datos de espera en urgencias para el periodo."
        return result

    standard_error = math.sqrt(var_c / n_c + var_b / n_b) or 1.0
    z = delta / standard_error
    significant = abs(z) >= WAIT_Z_THRESHOLD and abs(delta) >= MIN_WAIT_DELTA_MINUTES
    direction = "sube" if delta > 0 else "baja"

    # Factores ordenados por cuánto empujan en la dirección del cambio
    sign = 1 if delta >= 0 else -1
    drivers = sorted(decompose_change(base, current), key=lambda d: sign * d["contribution"], reverse=True)
    for d in drivers:
        level, shift = d["key"]
        d.update({
            "triage": level, "shift": shift, "label": f"{_triage_label(level).capitalize()} · {shift}",
            "type": "desempeño" if abs(d["performanceEffect"]) >= abs(d["mixEffect"]) else "mezcla",
            "shareOfChangePct": round(100 * d["contribution"] / delta, 1) if abs(delta) > 1e-9 else None,
        })
    result["drivers"] = [
        {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items() if k != "key"}
        for d in drivers
    ]
    result.update(zScore=round(z, 2), significant=significant,
                  direction=direction if significant else "estable")

    period = f"del {_fmt_date(w.current_start)} al {_fmt_date(w.current_end)}"
    if not significant:
        result["summary"] = (f"La espera promedio en urgencias {period} fue de {mean_c:.1f} min, "
                             f"dentro de lo habitual ({mean_b:.1f} min en las 4 semanas previas).")
        return result

    top = drivers[0]
    reason, action = _driver_sentence(top)
    verb = "subió" if delta > 0 else "bajó"
    share = f" (explica el {top['shareOfChangePct']:.0f} % del cambio)" if top["shareOfChangePct"] else ""
    summary = (f"La espera promedio en urgencias {verb} {abs(delta):.1f} min {period} "
               f"({mean_b:.1f} → {mean_c:.1f} min). Factor principal: {reason}{share}.")
    second = drivers[1] if len(drivers) > 1 else None
    if second and (second["shareOfChangePct"] or 0) >= SECONDARY_DRIVER_MIN_PCT:
        second_reason, _ = _driver_sentence(second)
        summary += f" También influyó que {second_reason} ({second['shareOfChangePct']:.0f} %)."
    result["summary"] = summary
    result["recommendation"] = action if delta > 0 else None
    return result


# --------------------------------------------------------------------------- #
# Alertas predictivas de demanda
# --------------------------------------------------------------------------- #

def poisson_z(observed: float, expected: float) -> float:
    """Desviación de un conteo respecto a lo esperado bajo un modelo de Poisson."""
    return (observed - expected) / math.sqrt(expected) if expected > 0 else 0.0


def project_next_week(weekly_counts: list[float]) -> float:
    """Tendencia lineal (mínimos cuadrados) sobre las semanas dadas, proyectada una semana."""
    x = np.arange(len(weekly_counts))
    slope, intercept = np.polyfit(x, weekly_counts, 1)
    return max(0.0, float(intercept + slope * len(weekly_counts)))


def _family_weekly_counts(conn: sqlite3.Connection, w: Windows) -> dict[str, list[int]]:
    """Ingresos por familia clínica en las 5 semanas: [ref-4, ref-3, ref-2, ref-1, actual]."""
    weeks = BASELINE_WEEKS + 1
    rows = conn.execute(
        "SELECT UPPER(SUBSTR(CodigoDiagnostico, 1, 1)) AS letter, "
        "CAST((julianday(?) - julianday(DATE(FechaIngreso))) / 7 AS INTEGER) AS weeks_ago, COUNT(*) AS n "
        "FROM VistaIngresos WHERE DATE(FechaIngreso) BETWEEN ? AND ? "
        "AND UPPER(CodigoDiagnostico) GLOB '[A-Z][0-9]*' "     # descarta 'No Registrado'
        "GROUP BY letter, weeks_ago",
        [w.current_end, w.baseline_start, w.current_end],
    ).fetchall()
    counts: dict[str, list[int]] = {}
    for r in rows:
        family = CLINICAL_FAMILIES.get(r["letter"])
        if family and family not in NON_CLINICAL_FAMILIES and 0 <= r["weeks_ago"] < weeks:
            series = counts.setdefault(family, [0] * weeks)
            series[weeks - 1 - r["weeks_ago"]] += r["n"]
    return counts


def _family_letters(family: str) -> list[str]:
    return [letter for letter, name in CLINICAL_FAMILIES.items() if name == family]


def medication_basket(conn: sqlite3.Connection, family: str, end: str, limit: int = BASKET_SIZE) -> list[dict]:
    """
    Medicamentos característicos de una familia clínica, aprendidos del consumo real.

    lift = (% de ingresos de la familia que usan el medicamento) / (% de todos los ingresos que lo usan).
    Un lift alto separa lo específico (salbutamol en respiratorias) de lo que usa todo el hospital
    (solución salina, catéteres).
    """
    letters = _family_letters(family)
    start = (date.fromisoformat(end) - timedelta(days=7 * BASKET_WEEKS - 1)).isoformat()
    placeholders = ", ".join("?" for _ in letters)
    excluded = ", ".join("?" for _ in EXCLUDED_BASKET_CATEGORIES)
    rows = conn.execute(
        f"""
        WITH adm AS (
            SELECT OidIngreso, UPPER(SUBSTR(CodigoDiagnostico, 1, 1)) IN ({placeholders}) AS fam
            FROM VistaIngresos WHERE DATE(FechaIngreso) BETWEEN ? AND ?
        ),
        totals AS (SELECT COUNT(*) AS n_all, SUM(fam) AS n_fam FROM adm),
        used AS (
            SELECT m.CodigoServicio AS code, a.fam, COUNT(DISTINCT m.OidIngreso) AS n_adm, SUM(m.Cantidad) AS qty
            FROM MedicamentoInsumo m JOIN adm a ON a.OidIngreso = m.OidIngreso
            GROUP BY m.CodigoServicio, a.fam
        )
        SELECT i.CodigoMedicamento AS code, i.NombreMedicamento AS name, i.Categoria AS category,
               i.StockActual AS stock, i.ConsumoDiarioPromedio AS daily,
               1.0 * SUM(CASE WHEN u.fam = 1 THEN u.n_adm END) / t.n_fam AS share,
               (1.0 * SUM(CASE WHEN u.fam = 1 THEN u.n_adm END) / t.n_fam) / (1.0 * SUM(u.n_adm) / t.n_all) AS lift,
               1.0 * SUM(CASE WHEN u.fam = 1 THEN u.qty END) / t.n_fam AS units_per_admission
        FROM used u JOIN totals t JOIN InventarioFarmacia i ON i.CodigoMedicamento = u.code
        WHERE i.Categoria NOT IN ({excluded}) AND t.n_fam > 0
        GROUP BY u.code
        HAVING share >= ? AND lift >= ?
        ORDER BY lift * share DESC
        LIMIT ?
        """,
        [*letters, start, end, *EXCLUDED_BASKET_CATEGORIES, BASKET_MIN_SHARE, BASKET_MIN_LIFT, limit],
    ).fetchall()
    return [dict(r) for r in rows]


def _order_quantity(daily: float, stock: float) -> int:
    """Unidades a pedir para llegar a TARGET_COVERAGE_DAYS días de cobertura."""
    return max(0, math.ceil(daily * TARGET_COVERAGE_DAYS - (stock or 0)))


def demand_alerts(conn: sqlite3.Connection, end: str | None = None) -> dict:
    """Familias clínicas con aumento significativo de ingresos y los medicamentos a reforzar."""
    w = build_windows(conn, end)
    alerts, watchlist = [], []
    for family, series in _family_weekly_counts(conn, w).items():
        baseline = series[:-1]
        expected = sum(baseline) / len(baseline)
        observed = series[-1]
        projected = project_next_week(series)
        z = poisson_z(observed, expected)
        growth = (projected - expected) / expected if expected else 0.0
        entry = {
            "family": family, "weeklyCounts": series, "baselineWeeklyAvg": round(expected, 1),
            "currentWeek": observed, "projectedNextWeek": round(projected), "growthPct": round(100 * growth, 1),
            "zScore": round(z, 2),
        }
        if expected >= MIN_WEEKLY_BASELINE and z >= DEMAND_Z_THRESHOLD and growth >= MIN_GROWTH:
            alerts.append(entry)
        elif expected >= MIN_WEEKLY_BASELINE and growth > 0:
            watchlist.append(entry)

    alerts.sort(key=lambda a: a["zScore"], reverse=True)
    alerts = alerts[:MAX_DEMAND_ALERTS]
    for alert in alerts:
        extra_weekly = alert["projectedNextWeek"] - alert["baselineWeeklyAvg"]
        medications = []
        for med in medication_basket(conn, alert["family"], w.current_end):
            # Consumo diario ajustado: el habitual más lo que consumirían los ingresos adicionales
            extra_daily = max(0.0, extra_weekly) / WINDOW_DAYS * (med["units_per_admission"] or 0)
            daily = (med["daily"] or 0) + extra_daily
            coverage = (med["stock"] or 0) / daily if daily else None
            medications.append({
                "code": med["code"], "name": med["name"], "category": med["category"],
                "lift": round(med["lift"], 1), "usedByPct": round(100 * med["share"], 1),
                "stock": med["stock"], "projectedDailyUse": round(daily, 1),
                "coverageDays": round(coverage, 1) if coverage is not None else None,
                "orderQuantity": _order_quantity(daily, med["stock"]),
            })
        alert["medications"] = medications
        alert["severity"] = "alta" if alert["zScore"] >= 2.33 else "media"
        alert["message"] = (
            f"Se proyectan {alert['projectedNextWeek']} ingresos por {alert['family'].lower()} la próxima "
            f"semana (+{alert['growthPct']:.0f} % frente al promedio de 4 semanas: "
            f"{alert['baselineWeeklyAvg']:.0f}/semana)."
        )
        to_order = [m for m in medications if m["orderQuantity"] > 0]
        if to_order:
            alert["action"] = "Reforzar stock de " + "; ".join(
                f"{_med_name(m['name'])} (cobertura {m['coverageDays']:.0f} días, pedir {m['orderQuantity']} und)"
                for m in to_order
            ) + "."
        elif medications:
            alert["action"] = ("Stock suficiente de los medicamentos asociados ("
                               + ", ".join(_med_name(m["name"]) for m in medications) + "); vigilar consumo.")
        else:
            alert["action"] = "Prever capacidad de atención para el aumento de ingresos."

    watchlist.sort(key=lambda a: a["growthPct"], reverse=True)
    return {
        "referenceDate": w.reference, "periodStart": w.current_start, "periodEnd": w.current_end,
        "method": ("Ingresos semanales por familia clínica (CIE-10); alerta si la semana actual supera a las "
                   "4 anteriores con significancia de Poisson (z ≥ 1,645) y la tendencia lineal proyecta "
                   "≥ 10 % de aumento. Medicamentos asociados por lift sobre el consumo real de 8 semanas."),
        "alerts": alerts,
        "watchlist": watchlist[:5],
    }


# --------------------------------------------------------------------------- #
# Alertas operativas (farmacia y camas)
# --------------------------------------------------------------------------- #

def medication_shortage_alert(conn: sqlite3.Connection) -> dict | None:
    """Alerta temprana de desabastecimiento: medicamentos con menos de 5 días de inventario."""
    low = conn.execute(
        "SELECT COUNT(*) FROM InventarioFarmacia WHERE DiasInventario < ?", [LOW_INVENTORY_DAYS]
    ).fetchone()[0]
    if not low:
        return None
    meds = conn.execute(
        "SELECT NombreMedicamento AS name, StockActual AS stock, ConsumoDiarioPromedio AS daily, "
        "DiasInventario AS days FROM InventarioFarmacia WHERE DiasInventario < ? "
        "ORDER BY ConsumoDiarioPromedio DESC LIMIT ?",
        [LOW_INVENTORY_DAYS, TOP_MEDS],
    ).fetchall()
    items = [{
        "name": m["name"], "stock": m["stock"], "daysOfInventory": m["days"],
        "dailyUse": round(m["daily"] or 0, 1), "orderQuantity": _order_quantity(m["daily"] or 0, m["stock"]),
    } for m in meds]
    return {
        "type": "desabastecimiento", "severity": "alta",
        "title": "Riesgo de desabastecimiento",
        "message": f"{low} medicamentos e insumos tienen menos de {LOW_INVENTORY_DAYS} días de inventario.",
        "action": "Priorizar la reposición de los de mayor consumo: " + "; ".join(
            f"{_med_name(i['name'])} (pedir {i['orderQuantity']} und)" for i in items[:3]) + ".",
        "items": items,
    }


def bed_capacity_alert(conn: sqlite3.Connection, w: Windows) -> dict | None:
    """
    Abrir camas y reasignar personal entre servicios: ocupación promedio de los últimos 7 días.
    Camas a habilitar = las necesarias para que la ocupación promedio baje al 85 %.
    """
    rows = conn.execute(
        "SELECT Servicio AS service, ROUND(AVG(PorcentajeOcupacion), 1) AS avg_pct, "
        "MAX(PorcentajeOcupacion) AS max_pct, AVG(CamasOcupadas) AS avg_occupied, MAX(CamasTotales) AS beds "
        "FROM OcupacionDiaria WHERE Fecha BETWEEN ? AND ? GROUP BY Servicio HAVING MAX(CamasTotales) >= ? "
        "ORDER BY avg_pct DESC",
        [w.current_start, w.current_end, MIN_SERVICE_BEDS],
    ).fetchall()
    saturated = [r for r in rows if (r["avg_pct"] or 0) >= HIGH_OCCUPANCY_PCT]
    if not saturated:
        return None
    items = [{
        "service": r["service"], "avgOccupancyPct": r["avg_pct"], "maxOccupancyPct": r["max_pct"],
        "beds": r["beds"],
        "bedsToOpen": max(1, math.ceil(r["avg_occupied"] / (HIGH_OCCUPANCY_PCT / 100) - r["beds"])),
    } for r in saturated]
    donors = [r for r in rows if (r["avg_pct"] or 0) < LOW_OCCUPANCY_PCT]

    action = "Habilitar camas: " + ", ".join(f"{i['service']} +{i['bedsToOpen']}" for i in items)
    action += ", o agilizar egresos (planeación temprana del alta) en esos servicios"
    if donors:
        action += (". Reasignar personal de enfermería de apoyo desde servicios con baja ocupación ("
                   + ", ".join(f"{d['service']} {d['avg_pct']:.0f} %" for d in donors[:3]) + ")")
    return {
        "type": "ocupacion", "severity": "alta" if any(i["avgOccupancyPct"] >= 95 for i in items) else "media",
        "title": (f"Ocupación alta sostenida en {len(items)} servicios" if len(items) > 1
                  else f"Ocupación alta sostenida en {items[0]['service']}"),
        "message": ("Ocupación promedio de los últimos 7 días por encima del 85 %: "
                    + ", ".join(f"{i['service']} {i['avgOccupancyPct']:.0f} %" for i in items) + "."),
        "action": action + ".",
        "items": items,
    }


def staff_reallocation_alert(wait: dict) -> dict | None:
    """Reasignar personal entre turnos de urgencias según la espera y la carga de cada turno."""
    shifts = [s for s in wait.get("shiftLoad", []) if s.get("currentAvgWait") is not None]
    if len(shifts) < 2:
        return None
    worst = max(shifts, key=lambda s: s["currentAvgWait"])
    best = min(shifts, key=lambda s: s["currentAvgWait"])
    gap = worst["currentAvgWait"] - best["currentAvgWait"]
    if gap < STAFF_MIN_WAIT_GAP_MINUTES or gap < STAFF_MIN_WAIT_GAP_PCT * best["currentAvgWait"]:
        return None
    return {
        "type": "personal", "severity": "media",
        "title": "Reasignación de personal en urgencias",
        "message": (f"El turno {worst['shift'].lower()} tiene la mayor espera ({worst['currentAvgWait']:.0f} min, "
                    f"{worst['currentPerDay']:.0f} pacientes/día) y el turno {best['shift'].lower()} la menor "
                    f"({best['currentAvgWait']:.0f} min, {best['currentPerDay']:.0f} pacientes/día)."),
        "action": (f"Reasignar personal de apoyo (triage y consulta) del turno {best['shift'].lower()} al turno "
                   f"{worst['shift'].lower()} ({worst['hours']}) o escalonar horarios para cubrir esa franja."),
        "items": [{k: s[k] for k in ("shift", "hours", "currentAvgWait", "currentPerDay")} for s in shifts],
    }


def surgery_scheduling_alert(conn: sqlite3.Connection, w: Windows) -> dict | None:
    """
    Optimización de la programación de quirófanos (últimas 4 semanas):
    nivelar la carga entre días hábiles y revisar las cirugías no realizadas.
    """
    start = (date.fromisoformat(w.current_end) - timedelta(days=SURGERY_WINDOW_DAYS - 1)).isoformat()
    rows = conn.execute(
        "SELECT cp.EstadoCirugia AS status, cp.Servicio AS service, "
        "COALESCE(cp.Fecha, DATE(i.FechaIngreso)) AS day "
        "FROM CirugiasProgramadas cp LEFT JOIN Ingresos i ON i.OidIngreso = cp.OidIngreso "
        "WHERE cp.EstadoCirugia <> 'Sin ingreso en el periodo' "
        # Las cirugías no realizadas no tienen fecha: se ubican por la fecha de ingreso (igual que el dashboard)
        "AND COALESCE(cp.Fecha, DATE(i.FechaIngreso)) BETWEEN ? AND ?",
        [start, w.current_end],
    ).fetchall()
    performed = [r for r in rows if r["status"] == "Realizada"]
    not_performed = [r for r in rows if r["status"] != "Realizada"]
    if not performed:
        return None

    weeks = SURGERY_WINDOW_DAYS / 7
    per_weekday = [0.0] * 7
    for r in performed:
        per_weekday[date.fromisoformat(r["day"]).weekday()] += 1 / weeks
    business = per_weekday[:5]
    mean_business = sum(business) / 5
    peak_day = max(range(5), key=lambda d: business[d])
    valley_day = min(range(5), key=lambda d: business[d])
    imbalance = (business[peak_day] - business[valley_day]) / mean_business if mean_business else 0.0
    cancellation_pct = 100 * len(not_performed) / len(rows)

    cancelled_by_service: dict[str, int] = {}
    for r in not_performed:
        cancelled_by_service[r["service"] or "Sin servicio"] = cancelled_by_service.get(r["service"] or "Sin servicio", 0) + 1
    worst_service = max(cancelled_by_service.items(), key=lambda kv: kv[1], default=None)

    if imbalance < SURGERY_IMBALANCE_PCT and cancellation_pct < SURGERY_CANCELLATION_PCT:
        return None
    actions = []
    if imbalance >= SURGERY_IMBALANCE_PCT:
        to_move = max(1, round((business[peak_day] - business[valley_day]) / 2))
        surgeries = "1 cirugía electiva" if to_move == 1 else f"unas {to_move} cirugías electivas"
        actions.append(f"Mover {surgeries} por semana del {WEEKDAYS[peak_day]} al "
                       f"{WEEKDAYS[valley_day]} para nivelar el uso de los quirófanos")
    if worst_service:
        actions.append(f"revisar las {worst_service[1]} cirugías no realizadas de {worst_service[0]} "
                       "(preparación prequirúrgica y disponibilidad de cama antes de programar)")
    severity = "media" if imbalance >= 0.3 or cancellation_pct >= SURGERY_CANCELLATION_PCT else "baja"
    return {
        "type": "cirugia", "severity": severity,
        "title": "Optimización de la programación de quirófanos",
        "message": (f"Últimas 4 semanas: {len(performed)} cirugías realizadas, {len(not_performed)} no realizadas "
                    f"({100 - cancellation_pct:.0f} % de cumplimiento). Carga desigual entre días hábiles: "
                    f"{WEEKDAYS[peak_day]} {business[peak_day]:.1f}/día frente a {WEEKDAYS[valley_day]} "
                    f"{business[valley_day]:.1f}/día."),
        "action": _sentence("; ".join(actions)),
        "items": [{"day": WEEKDAYS[d], "perDay": round(per_weekday[d], 1),
                   "vsAveragePct": round(100 * (per_weekday[d] - mean_business) / mean_business, 1) if mean_business else None}
                  for d in range(7)],
    }


def operational_alerts(conn: sqlite3.Connection, end: str | None = None, wait: dict | None = None) -> list[dict]:
    """Punto 7 del reto: desabastecimiento, camas, personal y quirófanos (solo las que aplican)."""
    w = build_windows(conn, end)
    wait = wait or wait_time_drivers(conn, end)
    alerts = [
        medication_shortage_alert(conn),
        bed_capacity_alert(conn, w),
        staff_reallocation_alert(wait),
        surgery_scheduling_alert(conn, w),
    ]
    return [a for a in alerts if a]


# --------------------------------------------------------------------------- #
# Resumen proactivo
# --------------------------------------------------------------------------- #

def build_briefing(conn: sqlite3.Connection, end: str | None = None) -> dict:
    """Resumen que el asistente muestra al abrir la aplicación: alertas ordenadas por prioridad."""
    demand = demand_alerts(conn, end)
    wait = wait_time_drivers(conn, end)
    items = [{
        "type": "demanda", "severity": a["severity"], "title": f"Pico de demanda: {a['family']}",
        "message": a["message"], "action": a["action"], "items": a["medications"],
    } for a in demand["alerts"]]
    if wait["significant"]:
        items.append({
            "type": "espera", "severity": "alta" if wait["deltaMinutes"] > 0 else "baja",
            "title": ("Aumento del tiempo de espera en urgencias" if wait["deltaMinutes"] > 0
                      else "Mejora del tiempo de espera en urgencias"),
            "message": wait["summary"],
            "action": wait["recommendation"], "items": wait["drivers"][:3],
        })
    items.extend(operational_alerts(conn, end, wait))
    items.sort(key=lambda i: SEVERITY_ORDER.get(i["severity"], 9))

    high = sum(1 for i in items if i["severity"] == "alta")
    if items:
        headline = (f"Analicé los datos al {_fmt_date(wait['periodEnd'])} y encontré {len(items)} "
                    f"alerta{'s' if len(items) != 1 else ''}"
                    + (f", {high} de prioridad alta." if high else "."))
    else:
        headline = f"Analicé los datos al {_fmt_date(wait['periodEnd'])}: no hay alertas activas."
    return {
        "referenceDate": wait["referenceDate"], "periodStart": wait["periodStart"],
        "periodEnd": wait["periodEnd"], "headline": headline, "items": items,
        "waitTime": {k: wait[k] for k in ("currentAvgMinutes", "baselineAvgMinutes", "deltaMinutes",
                                          "significant", "summary")},
    }
