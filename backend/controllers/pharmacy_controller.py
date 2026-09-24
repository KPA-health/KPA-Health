"""Controlador de farmacia: /pharmacy (contrato de front-kpa/js/services/pharmacyService.js)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.controllers.dependencies import require_permission
from backend.models import pharmacy_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse, ListResponse
from backend.schemas.resources import PharmacyItem, PharmacyUpdate
from backend.services.auth.permissions import PERM_OPERATIONS

router = APIRouter(prefix="/pharmacy", tags=["Farmacia"])


@router.get("", response_model=ListResponse[PharmacyItem])
def list_pharmacy_items(
    status: str | None = Query(default=None, description="Crítico | Bajo | Adecuado"),
    category: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=5000),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Inventario ordenado por urgencia; `count` es el total antes de aplicar `limit`."""
    data, total = pharmacy_model.list_items(conn, status, category, q, limit)
    return ListResponse[PharmacyItem](data=data, count=total)


@router.get("/{item_id}", response_model=ItemResponse[PharmacyItem])
def get_pharmacy_item(item_id: str, conn: sqlite3.Connection = Depends(get_db)):
    return ItemResponse[PharmacyItem](data=pharmacy_model.get_item(conn, item_id))


@router.put("/{item_id}", response_model=ItemResponse[PharmacyItem],
            dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_pharmacy_item(item_id: str, payload: PharmacyUpdate, conn: sqlite3.Connection = Depends(get_db)):
    """Stock digitado por un administrador (deja de ser simulado)."""
    return ItemResponse[PharmacyItem](data=pharmacy_model.update_item(conn, item_id, payload),
                                      message="Stock actualizado")
