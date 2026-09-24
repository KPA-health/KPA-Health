"""
Repositorio de farmacia (/pharmacy).

El consumo es real (MedicamentoInsumo); el stock es simulado de forma
determinista hasta que un usuario lo actualiza (ver semantic_layer._refresh_inventory).
El estado (Crítico/Bajo/Adecuado) es una columna generada en SQLite con la
misma regla que usa el mock del frontend: stock <= 50% del mínimo -> Crítico.
"""
from __future__ import annotations

import sqlite3

from backend.core.errors import NotFoundError
from backend.core.timeutils import now_str
from backend.schemas.resources import PharmacyItem, PharmacyUpdate

_ORDER = (
    "ORDER BY CASE Estado WHEN 'Crítico' THEN 0 WHEN 'Bajo' THEN 1 ELSE 2 END, "
    "DiasInventario IS NULL, DiasInventario, NombreMedicamento"
)


def _to_item(row: sqlite3.Row) -> PharmacyItem:
    return PharmacyItem(
        id=row["CodigoMedicamento"],
        name=row["NombreMedicamento"],
        generic=row["NombreMedicamento"],
        category=row["Categoria"],
        stock=row["StockActual"],
        min_stock=row["StockMinimo"],
        unit=row["Unidad"],
        batch=row["Lote"],
        expiry=row["FechaVencimiento"],
        status=row["Estado"],
        daily_consumption=row["ConsumoDiarioPromedio"],
        days_of_inventory=row["DiasInventario"],
        simulated_stock=bool(row["StockSimulado"]),
    )


def list_items(
    conn: sqlite3.Connection,
    status: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int | None = None,
) -> tuple[list[PharmacyItem], int]:
    where, params = [], []
    if status and status != "all":
        where.append("Estado = ?")
        params.append(status)
    if category and category != "all":
        where.append("Categoria = ?")
        params.append(category)
    if q:
        where.append("(NombreMedicamento LIKE ? OR CodigoMedicamento LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM InventarioFarmacia{clause}", params).fetchone()[0]
    sql = f"SELECT * FROM InventarioFarmacia{clause} {_ORDER}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return [_to_item(r) for r in conn.execute(sql, params)], total


def get_item(conn: sqlite3.Connection, item_id: str) -> PharmacyItem:
    row = conn.execute(
        "SELECT * FROM InventarioFarmacia WHERE CodigoMedicamento = ?", (item_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Insumo no encontrado")
    return _to_item(row)


def update_item(conn: sqlite3.Connection, item_id: str, data: PharmacyUpdate) -> PharmacyItem:
    get_item(conn, item_id)
    columns = {
        "stock": "StockActual", "min_stock": "StockMinimo", "batch": "Lote",
        "expiry": "FechaVencimiento", "unit": "Unidad",
    }
    fields = data.model_dump(exclude_unset=True)
    updates = {columns[k]: v for k, v in fields.items() if k in columns and v is not None}
    if updates:
        # Un stock digitado por un usuario deja de ser simulado
        if "StockActual" in updates or "StockMinimo" in updates:
            updates["StockSimulado"] = 0
        updates["ActualizadoEn"] = now_str()
        assignments = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE InventarioFarmacia SET {assignments} WHERE CodigoMedicamento = ?",
            (*updates.values(), item_id),
        )
        conn.commit()
    return get_item(conn, item_id)
