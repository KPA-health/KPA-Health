"""Pronósticos de demanda por familia clínica, sin llamadas a proveedores de IA.

Cada ejemplo usa únicamente conteos disponibles al cierre de su fecha de corte.
La validación reserva el tramo final y excluye del entrenamiento cualquier etiqueta
cuya ventana futura alcance ese tramo. Así se evita anticipar información futura.
"""
from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from backend.core.errors import BadRequestError
from backend.services.insights.insights_service import CLINICAL_FAMILIES, NON_CLINICAL_FAMILIES

HORIZONS = {"day": 1, "month": 30, "year": 365}
FEATURES = {
    "day": ["ingresos_ultimo_dia", "promedio_7_dias", "promedio_28_dias", "dia_semana_objetivo"],
    "month": ["ingresos_ultimo_dia", "promedio_7_dias", "promedio_28_dias", "mes_objetivo"],
    "year": ["ingresos_ultimo_dia", "promedio_7_dias", "promedio_28_dias", "ingresos_365_dias"],
}
MIN_TRAIN = 30
MIN_VALIDATION = 10
MIN_FAMILY_TOTAL = 30
VALIDATION_FRACTION = 0.15
TREES = 60


def _minimum_history_days(horizon: str) -> int:
    days = HORIZONS[horizon]
    first = 364 if horizon == "year" else 27
    origins = days + MIN_TRAIN + MIN_VALIDATION
    while origins - max(MIN_VALIDATION, math.ceil(origins * VALIDATION_FRACTION)) - days < MIN_TRAIN:
        origins += 1
    return first + days + origins


def _features(counts: list[int], origin: int, horizon: str, start: date) -> list[float]:
    """Variables conocidas hasta origin (inclusive); nunca consulta el objetivo."""
    target = start + timedelta(days=origin + 1)
    calendar = target.weekday() if horizon == "day" else target.month
    if horizon == "year":
        calendar = sum(counts[origin - 364:origin + 1])
    return [counts[origin], sum(counts[origin - 6:origin + 1]) / 7,
            sum(counts[origin - 27:origin + 1]) / 28, calendar]


def _fit_and_predict(counts: list[int], start: date, horizon: str) -> dict:
    days = HORIZONS[horizon]
    # 28 días previos para variables; 365 si se pide horizonte anual.
    first = 364 if horizon == "year" else 27
    last = len(counts) - days - 1
    origins = list(range(first, last + 1))
    validation_size = max(MIN_VALIDATION, math.ceil(len(origins) * VALIDATION_FRACTION))
    if len(origins) < MIN_TRAIN + MIN_VALIDATION + days:
        return {"status": "insufficient_data", "requiredDays": _minimum_history_days(horizon),
                "availableDays": len(counts)}

    validation_origins = origins[-validation_size:]
    first_validation = validation_origins[0]
    # La etiqueta de entrenamiento termina antes de la primera fecha de validación.
    train_origins = [i for i in origins if i + days < first_validation]
    if len(train_origins) < MIN_TRAIN:
        return {"status": "insufficient_data", "requiredDays": _minimum_history_days(horizon),
                "availableDays": len(counts)}

    def target(i: int) -> int:
        return sum(counts[i + 1:i + days + 1])

    def baseline(i: int) -> float:
        return sum(counts[i - days + 1:i + 1])

    x_train = [_features(counts, i, horizon, start) for i in train_origins]
    y_train = [target(i) for i in train_origins]
    x_valid = [_features(counts, i, horizon, start) for i in validation_origins]
    y_valid = np.array([target(i) for i in validation_origins])
    model = RandomForestRegressor(n_estimators=TREES, min_samples_leaf=3, max_depth=7,
                                  random_state=42, n_jobs=1)
    model.fit(x_train, y_train)
    rf_valid = np.maximum(0, model.predict(x_valid))
    simple_valid = np.array([baseline(i) for i in validation_origins])
    rf_mae = float(np.mean(np.abs(rf_valid - y_valid)))
    simple_mae = float(np.mean(np.abs(simple_valid - y_valid)))
    # El bosque se publica solamente si supera al último período observado.
    method = "random_forest" if rf_mae < simple_mae else "previous_period"
    last_origin = len(counts) - 1
    if method == "random_forest":
        # La evaluación quedó fijada arriba; para producción se aprovechan también
        # las ventanas ya observadas del tramo de validación.
        model.fit([_features(counts, i, horizon, start) for i in origins],
                  [target(i) for i in origins])
        forecast = float(model.predict([_features(counts, last_origin, horizon, start)])[0])
    else:
        forecast = baseline(last_origin)
    forecast = max(0, round(forecast))
    previous = baseline(last_origin)
    error = rf_mae if method == "random_forest" else simple_mae
    # El error empírico impide elevar variaciones pequeñas a alertas.
    minimum_count = {"day": 5, "month": 15, "year": 50}[horizon]
    alert = (method == "random_forest" and forecast >= minimum_count
             and forecast >= previous * 1.2 and forecast - previous >= max(2, 1.5 * error))
    return {
        "status": "ready", "method": method, "predictedAdmissions": forecast,
        "previousPeriodAdmissions": round(previous), "alert": alert,
        "validation": {"trainSamples": len(train_origins), "validationSamples": len(validation_origins),
                       "randomForestMae": round(rf_mae, 2), "previousPeriodMae": round(simple_mae, 2),
                       "selectedMae": round(error, 2)},
    }


def forecast_alerts(conn: sqlite3.Connection, horizon: str = "day", end: str | None = None) -> dict:
    """Pronostica ingresos por familia para el día o los próximos 30/365 días."""
    if horizon not in HORIZONS:
        raise BadRequestError("Horizonte inválido", {"allowed": list(HORIZONS)})
    max_row = conn.execute("SELECT MIN(DATE(FechaIngreso)), MAX(FechaIngreso) FROM Ingresos").fetchone()
    if not max_row or not max_row[0] or not max_row[1]:
        return {"status": "insufficient_data", "horizon": horizon, "horizonDays": HORIZONS[horizon],
                "referenceDate": None, "predictionStart": None, "predictionEnd": None,
                "features": FEATURES[horizon], "families": [], "alerts": []}
    first = date.fromisoformat(max_row[0])
    latest = date.fromisoformat(max_row[1][:10])
    # El último día puede estar incompleto en un extracto del HIS.
    default_end = latest - timedelta(days=1) if max_row[1][11:19] < "23:55:00" else latest
    try:
        cutoff = date.fromisoformat(end) if end else default_end
    except ValueError as exc:
        raise BadRequestError("Fecha inválida: use AAAA-MM-DD", {"end": end}) from exc
    if cutoff > default_end or cutoff < first:
        raise BadRequestError("La fecha debe estar dentro de días completos del HIS",
                              {"first": first.isoformat(), "latestComplete": default_end.isoformat()})

    rows = conn.execute(
        "SELECT DATE(FechaIngreso) AS day, UPPER(SUBSTR(CodigoDiagnostico, 1, 1)) AS code, COUNT(*) AS n "
        "FROM Ingresos WHERE FechaIngreso >= ? AND FechaIngreso < ? "
        "AND UPPER(CodigoDiagnostico) GLOB '[A-Z][0-9]*' GROUP BY day, code",
        (first.isoformat(), (cutoff + timedelta(days=1)).isoformat()),
    ).fetchall()
    length = (cutoff - first).days + 1
    by_family: dict[str, list[int]] = defaultdict(lambda: [0] * length)
    for row in rows:
        family = CLINICAL_FAMILIES.get(row["code"])
        if family and family not in NON_CLINICAL_FAMILIES:
            by_family[family][(date.fromisoformat(row["day"]) - first).days] += row["n"]

    families = []
    for family, counts in sorted(by_family.items()):
        if sum(counts) < MIN_FAMILY_TOTAL:
            continue
        result = _fit_and_predict(counts, first, horizon)
        families.append({"family": family, **result})
    days = HORIZONS[horizon]
    return {
        "status": "ready" if any(f["status"] == "ready" for f in families) else "insufficient_data",
        "horizon": horizon, "horizonDays": days, "referenceDate": cutoff.isoformat(),
        "predictionStart": (cutoff + timedelta(days=1)).isoformat(),
        "predictionEnd": (cutoff + timedelta(days=days)).isoformat(),
        "features": FEATURES[horizon], "families": families,
        "alerts": [f for f in families if f.get("alert")],
        "note": "Pronóstico estadístico de ingresos; no es una recomendación clínica. El horizonte mensual equivale a 30 días y el anual a 365.",
    }
