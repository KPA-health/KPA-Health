"""Controlador de insights: alertas predictivas, recomendaciones y causa raíz (/insights)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.models.db_connection import get_db
from backend.services.insights import insights_service

router = APIRouter(prefix="/insights", tags=["Insights"])

END_DATE_QUERY = Query(default=None, description="Último día a analizar (AAAA-MM-DD); por defecto, la fecha de referencia")


@router.get("/briefing")
def get_briefing(end: str | None = END_DATE_QUERY, conn: sqlite3.Connection = Depends(get_db)):
    """Resumen proactivo: todas las alertas activas ordenadas por prioridad, con su acción recomendada."""
    return {"data": insights_service.build_briefing(conn, end)}


@router.get("/wait-drivers")
def get_wait_drivers(end: str | None = END_DATE_QUERY, conn: sqlite3.Connection = Depends(get_db)):
    """Causa raíz: qué segmentos (triage x turno) explican el cambio de la espera en urgencias."""
    return {"data": insights_service.wait_time_drivers(conn, end)}


@router.get("/demand-alerts")
def get_demand_alerts(end: str | None = END_DATE_QUERY, conn: sqlite3.Connection = Depends(get_db)):
    """Alertas predictivas: picos de ingresos por familia clínica y medicamentos a reforzar."""
    return {"data": insights_service.demand_alerts(conn, end)}
