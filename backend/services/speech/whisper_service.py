"""
Proveedor de voz a texto con faster-whisper (100 % local y gratuito).

- Modelo 'small' (multilingüe) sobre CTranslate2; en CPU con int8 transcribe
  una pregunta de 3-5 s en ~1,5 s y no compite por la VRAM con el LLM local.
- El audio del navegador (webm/opus) se decodifica con PyAV (incluido en
  faster-whisper), sin necesidad de ffmpeg en el sistema.
- Política de idioma: se detecta el idioma; si con alta probabilidad NO es
  español se rechaza (el asistente solo atiende en español). Si la detección
  es dudosa se fuerza la transcripción en español.
- VAD (detección de voz) recorta silencios antes de transcribir.
"""
from __future__ import annotations

import io
import logging
import threading
import time

from starlette.concurrency import run_in_threadpool

from backend.core.config import VoiceSettings
from backend.core.errors import BadRequestError, PayloadTooLargeError, ServiceUnavailableError
from backend.services.speech.speech_provider import SpeechToTextProvider, TranscriptionResult

logger = logging.getLogger("medipulse.voice")

SPANISH = "es"
LANGUAGE_NAMES = {"en": "inglés", "pt": "portugués", "fr": "francés", "it": "italiano", "de": "alemán"}


class LanguageNotSupportedError(BadRequestError):
    """El audio está en un idioma distinto del español con alta probabilidad."""


class WhisperSpeechToText(SpeechToTextProvider):
    """Transcriptor local con carga perezosa y segura entre hilos del modelo Whisper."""

    name = "faster-whisper"

    def __init__(self, settings: VoiceSettings):
        self.settings = settings
        self.model_name = settings.model_size
        self._model = None
        self._device_used: str | None = None
        self._lock = threading.Lock()
        self._load_error: str | None = None

    # ------------------------------------------------------------------ carga

    def _load(self):
        """
        Carga el modelo una sola vez (double-checked locking): varias peticiones
        simultáneas no cargan dos copias del modelo en memoria.
        """
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # dependencia opcional
                self._load_error = "faster-whisper no está instalado (pip install faster-whisper)"
                raise ServiceUnavailableError(self._load_error) from exc

            candidates = self._device_candidates()
            last_error: Exception | None = None
            for device, compute_type in candidates:
                try:
                    started = time.perf_counter()
                    model = WhisperModel(self.settings.model_size, device=device, compute_type=compute_type)
                    self._model, self._device_used, self._load_error = model, f"{device}/{compute_type}", None
                    logger.info("Whisper '%s' cargado en %s (%.1f s)", self.settings.model_size,
                                self._device_used, time.perf_counter() - started)
                    return model
                except Exception as exc:  # p. ej. faltan librerías CUDA -> se intenta el siguiente
                    last_error = exc
                    logger.warning("No se pudo cargar Whisper en %s: %s", device, exc)
            self._load_error = f"No se pudo cargar el modelo de voz: {last_error}"
            raise ServiceUnavailableError(self._load_error)

    def _device_candidates(self) -> list[tuple[str, str]]:
        """Dispositivos a probar en orden; en GPU siempre queda la CPU como respaldo."""
        device, compute = self.settings.device, self.settings.compute_type
        if device == "cuda":
            return [("cuda", "float16" if compute == "auto" else compute), ("cpu", "int8")]
        if device == "auto":
            return [("cuda", "float16"), ("cpu", "int8")]
        return [("cpu", "int8" if compute == "auto" else compute)]

    def preload(self) -> None:
        """Carga en segundo plano al arrancar; un fallo solo se registra (se reintenta al usarla)."""
        try:
            self._load()
        except Exception as exc:  # noqa: BLE001 - la precarga nunca debe tumbar el servidor
            logger.warning("Precarga de Whisper fallida: %s", exc)

    def status(self) -> dict:
        return {
            "enabled": True,
            "model": f"whisper-{self.settings.model_size}",
            "device": self._device_used or self.settings.device,
            "loaded": self._model is not None,
            "detail": self._load_error or ("Listo" if self._model else "Se carga en la primera transcripción"),
        }

    # ---------------------------------------------------------- transcripción

    def _run(self, model, audio: bytes, language: str | None):
        """Transcribe con VAD (recorta silencios); language=None deja que Whisper detecte el idioma."""
        segments, info = model.transcribe(
            io.BytesIO(audio), language=language, beam_size=self.settings.beam_size,
            vad_filter=True, condition_on_previous_text=False,
        )
        if info.duration > self.settings.max_seconds:
            raise PayloadTooLargeError(f"El audio supera el máximo de {self.settings.max_seconds} segundos")
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, info

    def _transcribe_sync(self, audio: bytes) -> TranscriptionResult:
        model = self._load()
        started = time.perf_counter()
        try:
            text, info = self._run(model, audio, language=None)
        except (BadRequestError, PayloadTooLargeError, ServiceUnavailableError):
            raise
        except Exception as exc:  # audio corrupto o formato no decodificable por PyAV
            raise BadRequestError(f"No se pudo procesar el audio: {exc}") from exc

        if info.language != SPANISH:
            if info.language_probability >= self.settings.min_language_probability:
                name = LANGUAGE_NAMES.get(info.language, info.language)
                raise LanguageNotSupportedError(
                    f"Se detectó audio en {name}. El asistente solo atiende preguntas en español.",
                    {"detectedLanguage": info.language, "probability": round(info.language_probability, 2)},
                )
            # Detección dudosa (frases muy cortas): se transcribe forzando español
            text, info = self._run(model, audio, language=SPANISH)

        return TranscriptionResult(
            text=text,
            language=SPANISH,
            language_probability=round(info.language_probability, 3) if info.language_probability else None,
            duration_seconds=round(info.duration, 2),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            provider=self.name,
            model=f"whisper-{self.settings.model_size}",
            device=self._device_used or "cpu",
        )

    async def transcribe(self, audio: bytes, content_type: str, language: str = SPANISH) -> TranscriptionResult:
        """Valida tamaño y ejecuta la transcripción (CPU intensiva) fuera del event loop."""
        if not audio:
            raise BadRequestError("El audio está vacío")
        if len(audio) > self.settings.max_mb * 1024 * 1024:
            raise PayloadTooLargeError(f"El audio supera el máximo de {self.settings.max_mb} MB")
        return await run_in_threadpool(self._transcribe_sync, audio)
