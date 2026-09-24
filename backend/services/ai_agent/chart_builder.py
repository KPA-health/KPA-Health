"""
Datos de gráfico para el chat (renderizado determinista en el cliente con Chart.js).

Sin IA y sin tokens: el LLM no participa. El tipo de gráfico se decide con reglas sobre las
columnas y filas reales que devolvió SQLite (y palabras clave de la pregunta), así las cifras
del gráfico siempre coinciden con las de la tabla y la respuesta es la misma en cada ejecución.

Contrato de ``datos_grafico``: lista de objetos ``{"etiqueta": <categoría>, "<serie>": <número>, ...}``.
La primera clave es siempre ``etiqueta``; el resto son series numéricas con etiqueta legible.
Para ``gauge`` es un único punto ``{"etiqueta": <indicador>, "Valor": <0..100>}``.
"""
from __future__ import annotations

import re
from typing import Any

CHART_TYPES = ("bar", "pie", "line", "gauge")
LABEL_KEY = "etiqueta"

MAX_POINTS = 30          # más puntos no se leen en el globo del chat
MAX_PIE_SLICES = 8       # una dona con más porciones se dibuja como barras
MAX_SERIES = 3
MAX_PIVOT_SERIES = 8     # series de una tabla "mes x servicio" pivotada

_PERCENT_COLUMN = re.compile(r"(porcentaje|pct|tasa|%)", re.IGNORECASE)
_DATE_LIKE = re.compile(r"^\d{4}-\d{2}(-\d{2})?")
# Identificadores: son números pero no magnitudes (no se grafican)
_ID_COLUMN = re.compile(r"^(id|oid|codigo|cod)[_a-z]*$|(^|_)(id|oid|codigo)$", re.IGNORECASE)
# Pistas de la pregunta: "partes de un total" -> dona
_SHARE_WORDS = re.compile(r"distribuci[oó]n|proporci[oó]n|porcentaje|participaci[oó]n|reparto|composici[oó]n",
                          re.IGNORECASE)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_percent(column: str) -> bool:
    return bool(_PERCENT_COLUMN.search(column))


def _numeric_columns(columns: list[str], rows: list[list[Any]]) -> list[int]:
    """Índices de columnas con todos sus valores numéricos (o nulos) y que no son identificadores."""
    result = []
    for index, column in enumerate(columns):
        values = [row[index] for row in rows if row[index] is not None]
        if values and all(_is_number(v) for v in values) and not _ID_COLUMN.search(column):
            result.append(index)
    return result


def _same_unit(columns: list[str], indexes: list[int]) -> list[int]:
    """No mezcla porcentajes con conteos en el mismo eje: se conserva la unidad de la primera serie."""
    if not indexes:
        return indexes
    first_is_pct = _is_percent(columns[indexes[0]])
    return [i for i in indexes if _is_percent(columns[i]) == first_is_pct]


def _pivot(rows: list[list[Any]], x_index: int, group_index: int, value_index: int) -> list[dict[str, Any]] | None:
    """Tabla larga (mes, servicio, valor) -> una fila por mes y una serie por servicio."""
    groups = list(dict.fromkeys(str(row[group_index]) for row in rows))
    if len(groups) > MAX_PIVOT_SERIES:
        return None
    points: dict[str, dict[str, Any]] = {}
    for row in rows:
        x = str(row[x_index])
        points.setdefault(x, {LABEL_KEY: x, **{g: None for g in groups}})[str(row[group_index])] = row[value_index]
    return list(points.values())[:MAX_POINTS]


def _fits_pie(data: list[dict[str, Any]]) -> bool:
    """Una dona solo tiene sentido con pocas porciones, una serie y valores no negativos."""
    values = [v for point in data for k, v in point.items() if k != LABEL_KEY]
    return 2 <= len(data) <= MAX_PIE_SLICES and len(values) == len(data) and all(
        v is not None and v >= 0 for v in values)


def _single_row(columns: list[str], labels: list[str], row: list[Any], numeric: list[int],
                share: bool) -> tuple[str | None, list[dict[str, Any]]]:
    """KPI de una fila: porcentaje -> indicador; varias magnitudes comparables -> barras (o dona)."""
    percents = [i for i in numeric if _is_percent(columns[i]) and row[i] is not None and 0 <= row[i] <= 100]
    if percents:
        i = percents[0]
        return "gauge", [{LABEL_KEY: labels[i], "Valor": row[i]}]
    counts = [i for i in numeric if row[i] is not None]
    if len(counts) < 2:
        return None, []
    data = [{LABEL_KEY: labels[i], "Valor": row[i]} for i in counts]
    return ("pie" if share and _fits_pie(data) else "bar"), data


def build_chart(
    columns: list[str], labels: list[str], rows: list[list[Any]], question: str = "",
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Devuelve (tipo_grafico, datos_grafico). (None, []) cuando no hay nada que graficar:
    sin filas, una sola cifra que no es porcentaje o un listado sin magnitudes.
    """
    if not rows or not columns:
        return None, []
    numeric = _numeric_columns(columns, rows)
    if not numeric:
        return None, []
    share = bool(_SHARE_WORDS.search(question or ""))

    if len(rows) == 1:
        return _single_row(columns, labels, rows[0], numeric, share)

    categories = [i for i in range(len(columns)) if i not in numeric]
    # Sin columnas de texto, una primera columna entera (NivelTriage, mes, año) es la categoría, no una serie
    numeric_label = (not categories and len(numeric) >= 2 and numeric[0] == 0
                     and all(isinstance(row[0], int) for row in rows if row[0] is not None))
    if numeric_label:
        numeric, categories = numeric[1:], [0]

    label_index = categories[0] if categories else None
    series = _same_unit(columns, [i for i in numeric if i != label_index])[:MAX_SERIES]
    if not series:
        return None, []

    # Serie de tiempo por grupo (ej. mes x servicio): se pivota a una línea por grupo
    if len(categories) == 2:
        dated = [i for i in categories if isinstance(rows[0][i], str) and _DATE_LIKE.match(rows[0][i])]
        if len(dated) == 1:
            x_index = dated[0]
            group_index = next(i for i in categories if i != x_index)
            data = _pivot(rows, x_index, group_index, series[0])
            if data:
                return "line", data

    def label_of(row: list[Any], position: int) -> str:
        if label_index is None:
            return str(position + 1)
        if numeric_label:
            return f"{labels[0]} {row[0]}"   # "Nivel Triage 1" se lee mejor que "1" en la leyenda
        # Varias columnas de texto (ej. mes + servicio) se unen en una sola etiqueta
        parts = [str(row[i]) for i in categories[:2] if row[i] is not None]
        return " · ".join(parts) or "—"

    data = [
        {LABEL_KEY: label_of(row, position), **{labels[i]: row[i] for i in series}}
        for position, row in enumerate(rows[:MAX_POINTS])
    ]

    first = rows[0][label_index] if label_index is not None else None
    if isinstance(first, str) and _DATE_LIKE.match(first):
        return "line", data
    # Partes de un total: la pregunta pide una distribución o hay un porcentaje cuyas filas suman ~100
    # (la ocupación por servicio también es un porcentaje, pero no suma 100 y va en barras)
    has_share_column = any(
        _is_percent(columns[i]) and 98 <= sum(row[i] or 0 for row in rows) <= 102 for i in numeric
    )
    if (share or has_share_column) and _fits_pie(data):
        return "pie", data
    return "bar", data
