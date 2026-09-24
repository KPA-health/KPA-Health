"""
Detección ligera de idioma español/inglés (sin dependencias ni modelos).

Cuenta palabras funcionales de cada idioma y signos propios del español
(¿ ¡ ñ tildes). Es suficiente para preguntas cortas de un chat y no agrega
latencia; los casos dudosos ('unknown') los resuelve el modelo con su prompt.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SPANISH_WORDS = {
    "de", "la", "que", "el", "en", "y", "los", "del", "las", "un", "por", "con", "una", "su",
    "para", "es", "al", "lo", "como", "mas", "pero", "sus", "le", "ha", "si", "sin", "sobre",
    "este", "ya", "entre", "cuando", "todo", "esta", "ser", "son", "dos", "tambien", "fue",
    "muy", "hasta", "desde", "esta", "estan", "mi", "porque", "que", "cual", "cuales", "cuanto",
    "cuantos", "cuantas", "cuanta", "donde", "hay", "hoy", "ayer", "semana", "mes", "ultima",
    "ultimo", "ultimos", "ultimas", "promedio", "pacientes", "paciente", "camas", "cama",
    "medicamentos", "servicio", "servicios", "ocupadas", "ocupacion", "espera", "tiempo",
    "dame", "muestrame", "lista", "cuales", "tiene", "tienen", "mayor", "menor", "menos",
    "ingresos", "ingresados", "urgencias", "cirugias", "medicos", "dias", "se", "nos", "sera",
    "estado", "total", "numero", "quien", "quienes", "cuantos", "cual", "segun", "entre",
}
_ENGLISH_WORDS = {
    "the", "of", "and", "to", "in", "is", "you", "that", "it", "was", "for", "on", "are",
    "with", "they", "at", "be", "this", "have", "from", "or", "had", "by", "but", "what",
    "all", "were", "we", "when", "your", "can", "there", "an", "which", "how", "their", "will",
    "about", "many", "much", "then", "them", "these", "some", "would", "into", "has", "more",
    "than", "been", "who", "its", "now", "did", "get", "does", "do", "today", "yesterday",
    "week", "month", "last", "average", "wait", "waiting", "beds", "bed", "patients", "patient",
    "occupied", "show", "list", "give", "tell", "please", "please", "should", "could", "where",
    "why", "weather", "whats", "is", "am", "our", "my", "per", "which", "drugs", "medications",
    "stock", "surgeries", "doctors", "available", "number", "hello", "hi", "thanks",
}
_SPANISH_MARKS = re.compile(r"[¿¡ñÑáéíóúÁÉÍÓÚü]")
_TOKEN = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


@dataclass(frozen=True)
class LanguageResult:
    language: str  # "es" | "en" | "unknown"
    spanish_score: int
    english_score: int


def detect_language(text: str) -> LanguageResult:
    tokens = [_strip_accents(t.lower()) for t in _TOKEN.findall(text or "")]
    spanish = sum(t in _SPANISH_WORDS for t in tokens) + 2 * len(_SPANISH_MARKS.findall(text or ""))
    english = sum(t in _ENGLISH_WORDS for t in tokens)
    if english >= 2 and english > spanish * 1.5:
        language = "en"
    elif spanish >= 1 and spanish >= english:
        language = "es"
    else:
        language = "unknown"
    return LanguageResult(language, spanish, english)
