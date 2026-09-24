"""
Voz a texto (Speech-to-Text) — contrato común (patrón Strategy).

Flujo:
    audio del micrófono del navegador (webm/opus)
      -> SpeechToTextProvider.transcribe()   (faster-whisper local, modelo 'small')
      -> texto en español
      -> VoiceIntent.QUERY     -> el frontend lo pone en el chat (o NL2SQLService.ask)
         VoiceIntent.FORM_FILL -> (futuro) extracción estructurada hacia el wizard de ingreso

El proveedor se obtiene con get_speech_provider() (Singleton perezoso): el
modelo se carga una sola vez y se reutiliza en todas las peticiones.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache


class VoiceIntent(str, Enum):
    QUERY = "query"          # pregunta en lenguaje natural -> NL2SQL
    FORM_FILL = "form_fill"  # dictado para llenar un formulario (evolución futura)


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    language_probability: float | None
    duration_seconds: float
    elapsed_ms: int
    provider: str
    model: str
    device: str


class SpeechToTextProvider(ABC):
    name: str
    model_name: str

    @abstractmethod
    async def transcribe(self, audio: bytes, content_type: str, language: str = "es") -> TranscriptionResult:
        """Convierte audio a texto."""

    @abstractmethod
    def status(self) -> dict:
        """Estado del modelo (cargado, dispositivo) sin forzar su carga."""

    def preload(self) -> None:
        """Carga anticipada opcional del modelo."""


@lru_cache
def get_speech_provider() -> SpeechToTextProvider | None:
    """Proveedor de voz configurado; None si VOICE_ENABLED=false."""
    from backend.core.config import get_settings

    voice = get_settings().voice
    if voice is None or not voice.enabled:
        return None
    from backend.ai.speech.whisper import WhisperSpeechToText

    return WhisperSpeechToText(voice)
