"""Pronóstico de demanda: horizonte, corte temporal y disponibilidad de datos."""
from __future__ import annotations

from datetime import date

from backend.services.insights.forecast_service import _features, _fit_and_predict


def test_features_use_only_past_counts():
    history = list(range(50))
    before = _features(history, 35, "day", date(2026, 1, 1))
    history[36:] = [999] * 14
    assert _features(history, 35, "day", date(2026, 1, 1)) == before


def test_short_history_does_not_offer_annual_prediction():
    result = _fit_and_predict([3] * 150, date(2026, 1, 1), "year")
    assert result["status"] == "insufficient_data"
    assert result["requiredDays"] > result["availableDays"]


def test_daily_model_has_temporal_validation_and_nonnegative_forecast():
    counts = [12 + (i % 7) * 2 for i in range(145)]
    result = _fit_and_predict(counts, date(2026, 1, 1), "day")
    assert result["status"] == "ready"
    assert result["method"] in {"random_forest", "previous_period"}
    assert result["predictedAdmissions"] >= 0
    assert result["validation"]["trainSamples"] >= 30
    assert result["validation"]["validationSamples"] >= 10


def test_forecast_endpoint_reports_horizons_without_annual_claim(client):
    for horizon in ("day", "month", "year"):
        response = client.get("/api/insights/forecast-alerts", params={"horizon": horizon})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["horizon"] == horizon
        assert len(data["features"]) == 4
        assert data["predictionStart"] > data["referenceDate"]
        if horizon == "year":
            assert data["status"] == "insufficient_data"
            assert data["alerts"] == []


def test_forecast_rejects_future_cutoff(client):
    response = client.get("/api/insights/forecast-alerts", params={"end": "2099-01-01"})
    assert response.status_code == 400
