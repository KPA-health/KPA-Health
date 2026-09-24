"""Voz a texto: endpoint con proveedor falso y política de idioma de Whisper con un modelo simulado."""
from types import SimpleNamespace

import pytest

from backend.core.config import VoiceSettings
from backend.services.speech.speech_provider import TranscriptionResult
from backend.services.speech.whisper_service import LanguageNotSupportedError, WhisperSpeechToText


class FakeSpeech:
    name = "fake"
    model_name = "fake"

    async def transcribe(self, audio, content_type, language="es"):
        return TranscriptionResult("¿Cuántas camas de UCI están ocupadas hoy?", "es", 0.99, 2.5, 120,
                                   "fake", "whisper-small", "cpu/int8")

    def status(self):
        return {"enabled": True, "model": "whisper-small", "device": "cpu/int8", "loaded": True, "detail": "ok"}


def test_transcribe_endpoint_contract(client, monkeypatch):
    monkeypatch.setattr("backend.controllers.assistant_controller.get_speech_provider", lambda: FakeSpeech())
    response = client.post("/api/ai/transcribe", files={"audio": ("q.webm", b"audio", "audio/webm")})
    assert response.status_code == 200
    body = response.json()
    assert body["text"].startswith("¿Cuántas camas") and body["language"] == "es"
    assert body["durationSeconds"] == 2.5 and body["model"] == "whisper-small"


class _FakeModel:
    """Simula faster_whisper.WhisperModel: detecta un idioma y devuelve segmentos."""

    def __init__(self, detected: str, probability: float):
        self.detected, self.probability, self.calls = detected, probability, []

    def transcribe(self, audio, language=None, **kwargs):
        self.calls.append(language)
        lang = language or self.detected
        info = SimpleNamespace(language=lang, language_probability=1.0 if language else self.probability,
                               duration=3.0)
        return iter([SimpleNamespace(text=" texto transcrito ")]), info


def _whisper(model) -> WhisperSpeechToText:
    settings = VoiceSettings(enabled=True, model_size="small", device="cpu", compute_type="int8",
                             beam_size=1, preload=False, max_seconds=60, max_mb=10,
                             min_language_probability=0.75)
    provider = WhisperSpeechToText(settings)
    provider._model, provider._device_used = model, "cpu/int8"
    return provider


def test_whisper_rejects_confident_non_spanish_audio():
    with pytest.raises(LanguageNotSupportedError, match="inglés"):
        _whisper(_FakeModel("en", 0.99))._transcribe_sync(b"audio")


def test_whisper_forces_spanish_when_detection_is_doubtful():
    model = _FakeModel("pt", 0.40)
    result = _whisper(model)._transcribe_sync(b"audio")
    assert model.calls == [None, "es"] and result.text == "texto transcrito" and result.language == "es"


def test_whisper_accepts_spanish():
    model = _FakeModel("es", 0.97)
    result = _whisper(model)._transcribe_sync(b"audio")
    assert model.calls == [None] and result.language == "es"
