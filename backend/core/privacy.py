"""
Privacidad por diseño (Habeas Data, Ley 1581 de 2012).

Reglas que aplica todo el backend:
1. Los nombres reales NUNCA se almacenan: cada paciente se identifica con un
   seudónimo estable `Paciente_<IdPaciente>` (igual que la anonimización de setup_db.py).
2. El documento de identidad NUNCA se almacena en claro: se guarda un HMAC-SHA256
   con un secreto (PRIVACY_SALT). Permite buscar por documento sin poder revertirlo.
3. Ninguna respuesta de la API expone nombres ni documentos (se enmascaran).
4. El texto que produce la IA pasa por un depurador de patrones de identificación.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

from backend.core.config import get_settings

MASKED = "•••"

_DOC_NORMALIZER = re.compile(r"[^0-9A-Za-z]")

# "CC 1061234567", "cédula: 34.567.890", "documento de identidad No. 1234567", "DNI 74829104K"
_DOCUMENT_IN_TEXT = re.compile(
    r"\b(c\.?\s?c\.?|c[eé]dulas?|documentos?(?:\s+de\s+identidad)?|dni|t\.?\s?i\.?|pasaportes?|nit)"
    r"(\s*(?:n(?:[uú]mero|o|º|°)\.?)?\s*[:#]?\s*)"
    # dígitos con puntos/guiones; un espacio solo si le sigue otro dígito; letra final opcional (DNI)
    r"(\d(?:[\d.\-]|\s(?=\d)){4,}[A-Za-z]?)(?![A-Za-z])",
    re.IGNORECASE,
)

# Columnas de resultados que NO contienen datos personales aunque su nombre lo sugiera
_SAFE_COLUMN_TOKENS = (
    "medicament", "diagnost", "servicio", "cama", "grupo", "subgrupo", "area", "especialidad",
    "categoria", "insumo", "procedimiento", "municipio", "departamento", "asegurador", "regimen",
)
_PERSONAL_COLUMN = re.compile(
    r"(nombre|apellido|document|cedula|dni|identificacion|telefono|celular|email|correo|"
    r"direccion|nacimiento|pasaporte)"
)


def _normalize(text: str) -> str:
    """Minúsculas sin tildes, para comparar nombres de columnas sin importar su escritura."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def patient_pseudonym(patient_id: int | str | None) -> str:
    """Seudónimo estable del paciente: nunca se muestra ni se guarda su nombre real."""
    return f"Paciente_{patient_id}" if patient_id not in (None, "") else "Paciente anónimo"


def hash_document(document: str) -> str:
    """
    HMAC-SHA256 del documento normalizado (sin espacios, puntos ni guiones).

    Se usa HMAC con secreto (y no un SHA-256 simple) porque el espacio de cédulas
    es pequeño: sin el secreto, un atacante podría precalcular todos los hashes.
    """
    normalized = _DOC_NORMALIZER.sub("", document or "").upper()
    secret = get_settings().privacy_salt.encode("utf-8")
    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def looks_like_document(text: str) -> bool:
    """Heurística: 5-15 caracteres alfanuméricos con al menos 5 dígitos."""
    normalized = _DOC_NORMALIZER.sub("", text or "")
    return 5 <= len(normalized) <= 15 and sum(c.isdigit() for c in normalized) >= 5


def mask_document(document_type: str | None) -> str:
    """Documento enmascarado para la API: solo se revela el tipo (CC, TI...)."""
    return f"{document_type or 'Doc.'} {MASKED}"


def is_personal_column(column_name: str) -> bool:
    """True si el nombre de la columna sugiere un dato personal (nombre, documento, teléfono...)."""
    normalized = _normalize(column_name).replace("_", "").replace(" ", "")
    if any(token in normalized for token in _SAFE_COLUMN_TOKENS):
        return False
    return bool(_PERSONAL_COLUMN.search(normalized))


def scrub_text(text: str) -> str:
    """Enmascara números de documento que aparezcan en un texto libre."""
    if not text:
        return text
    return _DOCUMENT_IN_TEXT.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASKED}", text)


def mask_personal_columns(columns: list[str], rows: list[list]) -> tuple[list[list], list[str]]:
    """Defensa en profundidad: si una columna parece personal, sus valores se enmascaran."""
    personal = [i for i, col in enumerate(columns) if is_personal_column(col)]
    if not personal:
        return rows, []
    masked_rows = [[MASKED if i in personal else value for i, value in enumerate(row)] for row in rows]
    return masked_rows, [columns[i] for i in personal]
