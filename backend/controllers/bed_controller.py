"""Controlador de camas: /rooms (contrato de frontend/js/services/roomService.js)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.controllers.dependencies import require_permission
from backend.models import bed_model
from backend.models.db_connection import get_db
from backend.schemas.common import ItemResponse, SuccessResponse
from backend.schemas.resources import BedStatusUpdate, Wing
from backend.services.auth.permissions import PERM_OPERATIONS

router = APIRouter(prefix="/rooms", tags=["Camas"])


@router.get("", response_model=ItemResponse[list[Wing]])
def list_rooms(conn: sqlite3.Connection = Depends(get_db)):
    """Camas agrupadas por servicio/área con su estado a la fecha de referencia."""
    return ItemResponse[list[Wing]](data=bed_model.list_rooms(conn))


@router.put("/bed-status", response_model=SuccessResponse,
            dependencies=[Depends(require_permission(PERM_OPERATIONS))])
def update_bed_status(payload: BedStatusUpdate, conn: sqlite3.Connection = Depends(get_db)):
    """Estado manual de una cama ('Auto' vuelve al estado calculado desde el HIS)."""
    bed_model.update_bed_status(conn, payload)
    return SuccessResponse(message="Estado de cama modificado")
