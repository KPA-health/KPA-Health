"""
Voz a texto (Speech-to-Text) — contrato común (patrón Strategy).

Flujo:
    audio del micrófono del navegador (webm/opus)
      -> SpeechToTextProvider.transcribe()   (faster-whisper local, modelo 'small')
      -> texto en español
      -> VoiceIntent.QUERY     -> el frontend lo pone en el chat (o NL2SQLAgent.ask)
         VoiceIntent.FORM_FILL -> (futuro) extracción estructurada hacia el wizard de ingreso

El proveedor se obtiene con get_speech_provider() (Singleton perezoso): el
modelo se carga una sola vez y se reutiliza en todas las peticiones.

Por qué está aislado: faster-whisper es una dependencia pesada y opcional. Ningún
otro módulo lo importa directamente; si no está instalado, solo la voz queda
deshabilitada y el resto de la API funciona igual.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from backend.core.config import get_settings


class VoiceIntent(str, Enum):
    QUERY = "query"          # pregunta en lenguaje natural -> NL2SQL
    FORM_FILL = "form_fill"  # dictado para llenar un formulario (evolución futura)


@dataclass(frozen=True)
class TranscriptionResult:
    """Texto transcrito y metadatos de la transcripción."""
    text: str
    language: str
    language_probability: float | None
    duration_seconds: float
    elapsed_ms: int
    provider: str
    model: str
    device: str


class SpeechToTextProvider(ABC):
    """Contrato de cualquier motor de voz a texto."""
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
    voice = get_settings().voice
    if voice is None or not voice.enabled:
        return None
    # Import perezoso: faster-whisper solo se importa si la voz está habilitada
    from backend.services.speech.whisper_service import WhisperSpeechToText

    return WhisperSpeechToText(voice)
