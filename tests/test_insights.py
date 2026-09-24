"""Pruebas del valor añadido: causa raíz, alertas predictivas y resumen proactivo."""
from __future__ import annotations

import math

import pytest

from backend.services.insights.insights_service import (
    Segment, decompose_change, poisson_z, project_next_week,
)


def _overall_mean(segments: dict) -> float:
    total = sum(s.n for s in segments.values())
    return sum(s.n * s.mean for s in segments.values()) / total


def test_decomposition_adds_up_to_the_total_change():
    base = {(3, "Noche"): Segment(100, 40.0, 0), (4, "Tarde"): Segment(300, 60.0, 0)}
    current = {(3, "Noche"): Segment(200, 70.0, 0), (4, "Tarde"): Segment(300, 60.0, 0),
               (2, "Mañana"): Segment(50, 30.0, 0)}           # segmento nuevo en el periodo actual
    rows = decompose_change(base, current)
    delta = _overall_mean(current) - _overall_mean(base)
    assert math.isclose(sum(r["contribution"] for r in rows), delta, abs_tol=1e-9)


def test_decomposition_separates_mix_from_performance():
    base = {(3, "Noche"): Segment(100, 40.0, 0), (4, "Tarde"): Segment(100, 60.0, 0)}
    # Misma mezcla de pacientes, pero triage 3 de noche espera 20 min más -> solo efecto desempeño
    slower = {(3, "Noche"): Segment(100, 60.0, 0), (4, "Tarde"): Segment(100, 60.0, 0)}
    by_key = {r["key"]: r for r in decompose_change(base, slower)}
    assert by_key[(3, "Noche")]["performanceEffect"] == pytest.approx(10.0)
    assert by_key[(3, "Noche")]["mixEffect"] == pytest.approx(0.0)

    # Mismas esperas, pero llegan más pacientes del segmento lento -> solo efecto mezcla
    more_slow = {(3, "Noche"): Segment(100, 40.0, 0), (4, "Tarde"): Segment(300, 60.0, 0)}
    rows = decompose_change(base, more_slow)
    assert sum(r["performanceEffect"] for r in rows) == pytest.approx(0.0)
    assert sum(r["mixEffect"] for r in rows) == pytest.approx(5.0)


def test_poisson_z_and_linear_projection():
    assert poisson_z(20, 16) == pytest.approx(1.0)
    assert poisson_z(5, 0) == 0.0
    assert project_next_week([10, 12, 14, 16, 18]) == pytest.approx(20.0)
    assert project_next_week([10, 5, 0, 0, 0]) >= 0.0          # nunca proyecta ingresos negativos


@pytest.mark.parametrize("endpoint", ["/api/insights/briefing", "/api/insights/wait-drivers",
                                      "/api/insights/demand-alerts"])
def test_insights_endpoints_respond(client, endpoint):
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.json()["data"]["referenceDate"]


def test_briefing_contract(client):
    data = client.get("/api/insights/briefing").json()["data"]
    assert data["headline"].startswith("Analicé los datos")
    for item in data["items"]:
        assert item["severity"] in {"alta", "media", "baja"}
        assert item["title"] and item["message"]


def test_wait_drivers_explain_the_whole_change(client):
    data = client.get("/api/insights/wait-drivers").json()["data"]
    if data["drivers"]:
        total = sum(d["contribution"] for d in data["drivers"])
        assert total == pytest.approx(data["deltaMinutes"], abs=0.1)
    assert {s["shift"] for s in data["shiftLoad"]} == {"Mañana", "Tarde", "Noche"}


def test_invalid_end_date_is_rejected(client):
    response = client.get("/api/insights/briefing", params={"end": "21-09-2026"})
    assert response.status_code == 400
