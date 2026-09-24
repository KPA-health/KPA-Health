"""
Guardrails de SALIDA: toda respuesta (modelo local o nube) pasa por aquí.

1. Depura datos personales (documentos en texto libre).
2. Reemplaza jerga técnica ("filas", "base de datos", "SQL", ...) por lenguaje
   del negocio ("resultados", "información del hospital", ...).
3. Si aún quedan términos prohibidos o la respuesta no está en español, se
   descarta y se usa una respuesta determinista construida con los datos.
El detalle técnico (SQL) solo se muestra si el usuario activa esa vista.
"""
from __future__ import annotations

import re
from typing import Any

from backend.ai.guardrails import messages
from backend.ai.guardrails.language import detect_language
from backend.core.privacy import scrub_text

# "consulta" también es un término médico (consulta externa, motivo de consulta):
# solo se considera técnico cuando NO va acompañado de un calificador clínico.
_CLINICAL_CONSULTA = (
    r"(?!\s+(externas?|m[eé]dicas?|de urgencias?|especializadas?|prioritarias?|ambulatorias?|"
    r"pedi[aá]tricas?|generales?|de control|de primera vez|diferidas?))"
)
_NOT_REASON = r"(?<!motivo de )(?<!motivos de )"

# (patrón, reemplazo) aplicados en orden
_REPLACEMENTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(la|esta|dicha|mi)\s+consulta(\s+sql)?\s+(devolvi[oó]|retorn[oó]|arroj[oó]|"
                r"mostr[oó]|muestra|indica|encontr[oó]|dio como resultado)\s*", re.I), "se encontraron "),
    (re.compile(r"\bseg[uú]n\s+(la|esta|dicha)\s+consulta" + _CLINICAL_CONSULTA, re.I), "según los datos del hospital"),
    (re.compile(r"\b(en|de)\s+la\s+bases?\s+de\s+datos\b", re.I), r"\1 la información del hospital"),
    (re.compile(r"\bbases?\s+de\s+datos\b", re.I), "información del hospital"),
    (re.compile(r"\bconsultas?\s+sql\b", re.I), "búsqueda"),
    (re.compile(r"\bsql\b", re.I), ""),
    (re.compile(r"\bfilas\b", re.I), "resultados"),
    (re.compile(r"\bfila\b", re.I), "resultado"),
    (re.compile(r"\bregistros\b", re.I), "casos"),
    (re.compile(r"\bregistro\b", re.I), "caso"),
    (re.compile(r"\btablas\b", re.I), "listados"),
    (re.compile(r"\btabla\b", re.I), "listado"),
    (re.compile(r"\bcolumnas\b", re.I), "datos"),
    (re.compile(r"\bcolumna\b", re.I), "dato"),
    (re.compile(_NOT_REASON + r"\b(la|esta|dicha)\s+consulta\b" + _CLINICAL_CONSULTA, re.I), "la búsqueda"),
    # Términos en inglés que un modelo podría colar
    (re.compile(r"\brows?\b", re.I), "resultados"),
    (re.compile(r"\brecords?\b", re.I), "casos"),
    (re.compile(r"\bdatabases?\b", re.I), "información del hospital"),
    (re.compile(r"\bquer(y|ies)\b", re.I), "búsqueda"),
    (re.compile(r"\btables?\b", re.I), "listado"),
    (re.compile(r"\bcolumns?\b", re.I), "dato"),
]

# Razonamiento interno filtrado (modelos "thinking" que piensan en inglés antes de responder)
REASONING_LEAK = re.compile(
    r"^\s*(okay|ok|alright|so,|let'?s|let me|first,|hmm+|well,|wait,)"
    r"|\b(the user (is asking|wants|asked|provided)|i need to|i should|i will|let me (check|think|look|see))\b"
    r"|</?think>",
    re.IGNORECASE,
)


def looks_like_reasoning(text: str) -> bool:
    return bool(REASONING_LEAK.search(text or ""))


FORBIDDEN = re.compile(
    r"\b(filas?|registros?|bases?\s+de\s+datos|tablas?|columnas?|sql|quer(y|ies)|rows?|databases?|"
    r"tables?|columns?|records?)\b"
    r"|" + _NOT_REASON + r"\bconsultas?\b" + _CLINICAL_CONSULTA,
    re.IGNORECASE,
)


def contains_forbidden_terms(text: str) -> bool:
    return bool(FORBIDDEN.search(text or ""))


def _tidy(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text).strip()
    return text[:1].upper() + text[1:] if text else text


def sanitize_text(text: str) -> str:
    cleaned = scrub_text(text or "")
    for pattern, replacement in _REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return _tidy(cleaned)


def _format_value(value: Any) -> str:
    if value is None:
        return "sin dato"
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return str(value)


_DESCRIPTIVE_LABEL = re.compile(r"(medicamento|diagn|servicio|especialidad|área|area|categor|quirófano|turno|estado)", re.I)
_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\w])|(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def _descriptive_column(labels: list[str], rows: list[list[Any]]) -> int:
    for i, label in enumerate(labels):
        if _DESCRIPTIVE_LABEL.search(label) and rows and isinstance(rows[0][i], str):
            return i
    return 0


def deterministic_answer(labels: list[str], rows: list[list[Any]], row_count: int | None = None,
                         limit_hit: bool = False) -> str:
    """Respuesta en español construida solo con los datos (sin términos técnicos)."""
    if not rows:
        return messages.NO_RESULTS
    if len(rows) == 1 and len(labels) <= 5:
        parts = [f"{label}: {_format_value(value)}" for label, value in zip(labels, rows[0])]
        return "; ".join(parts) + "."
    total = row_count if row_count is not None else len(rows)
    quantity = f"al menos {_format_value(total)}" if limit_hit else _format_value(total)
    column = _descriptive_column(labels, rows)
    examples = ", ".join(_format_value(row[column]) for row in rows[:3])
    return f"Encontré {quantity} resultados. Los primeros son: {examples}."


def _as_number(token: str) -> float | None:
    token = token.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", token):      # 1.305 o 1.305,5 (miles con punto)
        token = token.replace(".", "").replace(",", ".")
    else:
        token = token.replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def ungrounded_numbers(answer: str, rows: list[list[Any]], row_count: int | None, question: str,
                       reference_date: str | None = None) -> list[str]:
    """
    Verificación de cifras (anti-alucinación): cada número de la respuesta debe existir en los
    datos, en la pregunta, en el total de resultados o en la fecha de referencia.
    """
    allowed: set[float] = set()
    sources = [str(row_count or 0), question or "", reference_date or ""]
    for row in rows:
        for cell in row:
            if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                allowed.update({float(cell), round(float(cell), 1), float(round(cell)), round(float(cell) * 100, 1)})
            elif cell is not None:
                sources.append(str(cell))
    for text in sources:
        for token in re.findall(r"\d+(?:[.,]\d+)?", text):
            value = _as_number(token)
            if value is not None:
                allowed.add(value)
    missing = []
    for match in _NUMBER.finditer(answer or ""):
        value = _as_number(match.group(0))
        if value is None or value <= 10:        # cantidades pequeñas y ordinales ("5 principales")
            continue
        if not any(abs(value - a) <= max(0.051, abs(a) * 0.001) for a in allowed):
            missing.append(match.group(0))
    return missing


def guard_answer(answer: str, labels: list[str], rows: list[list[Any]], row_count: int | None = None,
                 question: str = "", reference_date: str | None = None,
                 limit_hit: bool = False) -> tuple[str, list[str]]:
    """Devuelve (respuesta segura, avisos técnicos)."""
    warnings: list[str] = []
    cleaned = sanitize_text(answer)
    if cleaned != (answer or "").strip():
        warnings.append("La respuesta se depuró para no mostrar términos técnicos ni datos personales.")
    invented = ungrounded_numbers(cleaned, rows, row_count, question, reference_date) if cleaned else []
    if invented:
        warnings.append(f"Cifras no respaldadas por los datos: {', '.join(invented)}.")
    unsafe = (
        not cleaned
        or len(cleaned) > 700                      # una respuesta breve no ocupa más de 3 frases
        or looks_like_reasoning(answer)            # razonamiento interno filtrado
        or contains_forbidden_terms(cleaned)       # jerga técnica que no se pudo reemplazar
        or detect_language(cleaned).language != "es"  # solo se aceptan respuestas claramente en español
        or bool(invented)                          # cifras inventadas por el modelo
    )
    if unsafe:
        warnings.append("Se usó una respuesta construida directamente con los datos.")
        return deterministic_answer(labels, rows, row_count, limit_hit), warnings
    return cleaned, warnings
