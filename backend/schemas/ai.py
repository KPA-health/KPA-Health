"""DTOs del asistente IA (NL2SQL y voz): contrato JSON con aiService.js e index.html."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.schemas.common import CamelModel


class AIQueryRequest(CamelModel):
    question: str = Field(min_length=2, max_length=500,
                          pattern=r"^[^<>\x00-\x08\x0b\x0c\x0e-\x1f]*$",
                          description="Pregunta en lenguaje natural sin etiquetas HTML ni caracteres de control")
    mode: Literal["local", "cloud"] | None = Field(
        default=None, description="local = Qwen vía Ollama; cloud = Gemini. Vacío = AI_DEFAULT_MODE"
    )
    summarize: bool | None = Field(
        default=None, description="Redactar la respuesta con el LLM (por defecto AI_SUMMARIZE_RESULTS)"
    )


class AIAttempt(CamelModel):
    sql: str | None = None
    error: str


class AIQueryResponse(CamelModel):
    success: bool
    question: str
    mode: str
    provider: str
    model: str
    answer: str
    explanation: str
    sql: str | None
    category: str = Field(
        description="hospital | greeting | out_of_scope | unsupported_language | personal_data | empty"
    )
    blocked_by: str | None = Field(default=None, description="None | input_guard | model")
    columns: list[str]
    column_labels: list[str] = Field(default_factory=list, description="Etiquetas legibles en español")
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    attempts: list[AIAttempt]
    timings: dict[str, int]
    reference_date: str | None
    fallback_used: bool
    warnings: list[str]
    # Claves en español y snake_case (alias explícito): contrato de visualización del chat
    mensaje_texto: str = Field(default="", alias="mensaje_texto", description="Respuesta en lenguaje natural")
    datos_grafico: list[dict[str, Any]] = Field(
        default_factory=list, alias="datos_grafico",
        description='Puntos del gráfico: [{"etiqueta": ..., "<serie>": número}], armados con las filas reales',
    )
    tipo_grafico: Literal["bar", "pie", "line", "gauge"] | None = Field(
        default=None, alias="tipo_grafico", description="Gráfico elegido por código (sin IA); null = sin gráfico"
    )


class AIProviderStatus(CamelModel):
    mode: str
    provider: str
    model: str
    available: bool
    detail: str


class VoiceStatus(CamelModel):
    enabled: bool
    model: str | None = None
    device: str | None = None
    loaded: bool = False
    detail: str | None = None


class AIProvidersResponse(CamelModel):
    default_mode: str
    allow_fallback: bool
    providers: list[AIProviderStatus]
    voice_enabled: bool = False
    voice: VoiceStatus | None = None


class TranscriptionResponse(CamelModel):
    text: str
    language: str
    language_probability: float | None = None
    duration_seconds: float
    elapsed_ms: int
    model: str
    device: str
