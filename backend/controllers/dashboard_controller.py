"""Controlador del tablero BI: /dashboard (vista ejecutiva) y /stats (KPIs rápidos)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.models import dashboard_model, stats_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse
from backend.schemas.resources import Stats

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard BI"])
stats_router = APIRouter(prefix="/stats", tags=["Estadísticas"])


@dashboard_router.get("")
def get_dashboard(
    period: str = Query(default="today", description="today | 7d | 30d"),
    service: str = Query(default="all", description="'all' o un servicio, ej. 'Urgencias'"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """KPIs, tendencias, distribución, capacidad, censo y stock crítico en una sola respuesta."""
    return {"data": dashboard_model.get_dashboard(conn, period, service)}


@stats_router.get("", response_model=ItemResponse[Stats])
def get_stats(conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Stats](data=stats_model.get_stats(conn))
