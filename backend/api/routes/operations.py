"""/rooms, /pharmacy, /stats y /dashboard — contratos del mock de apiClient.js."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.permissions import PERM_OPERATIONS
from backend.core.database import get_db
from backend.repositories import dashboard as dashboard_repo
from backend.repositories import pharmacy as pharmacy_repo
from backend.repositories import rooms as rooms_repo
from backend.repositories import stats as stats_repo
from backend.schemas.common import ItemResponse, ListResponse, SuccessResponse
from backend.schemas.resources import BedStatusUpdate, PharmacyItem, PharmacyUpdate, Stats, Wing

rooms_router = APIRouter(prefix="/rooms", tags=["Camas"])
pharmacy_router = APIRouter(prefix="/pharmacy", tags=["Farmacia"])
stats_router = APIRouter(prefix="/stats", tags=["Estadísticas"])


@rooms_router.get("", response_model=ItemResponse[list[Wing]])
def list_rooms(conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[list[Wing]](data=rooms_repo.list_rooms(conn))


@rooms_router.put("/bed-status", response_model=SuccessResponse,
                  dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_bed_status(payload: BedStatusUpdate, conn: sqlite3.Connection = Depends(get_db)):
    rooms_repo.update_bed_status(conn, payload)
    return SuccessResponse(message="Estado de cama modificado")


@pharmacy_router.get("", response_model=ListResponse[PharmacyItem])
def list_pharmacy(
    status: str | None = Query(default=None, description="Crítico | Bajo | Adecuado"),
    category: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=5000),
    conn: sqlite3.Connection = Depends(get_db),
):
    data, total = pharmacy_repo.list_items(conn, status, category, q, limit)
    return ListResponse[PharmacyItem](data=data, count=total)


@pharmacy_router.get("/{item_id}", response_model=ItemResponse[PharmacyItem])
def get_pharmacy_item(item_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[PharmacyItem](data=pharmacy_repo.get_item(conn, item_id))


@pharmacy_router.put("/{item_id}", response_model=ItemResponse[PharmacyItem],
                     dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_pharmacy_item(item_id: str, payload: PharmacyUpdate, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[PharmacyItem](data=pharmacy_repo.update_item(conn, item_id, payload),
                                      message="Stock actualizado")


@stats_router.get("", response_model=ItemResponse[Stats])
def get_stats(conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[Stats](data=stats_repo.get_stats(conn))


# ------------------------------- Dashboard BI --------------------------------

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard BI"])


@dashboard_router.get("")
def get_dashboard(
    period: str = Query(default="today", description="today | 7d | 30d"),
    service: str = Query(default="all", description="'all' o un servicio, ej. 'Urgencias'"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """KPIs, tendencias, distribución, capacidad, censo y stock crítico en una sola respuesta."""
    return {"data": dashboard_repo.get_dashboard(conn, period, service)}
