"""
Controlador del asistente IA: /ai/* (NL2SQL con switch Local/Nube y voz a texto local).

Solo orquesta: la lógica vive en services/ai_agent (NL2SQLAgent) y
services/speech (Whisper). Los errores de esos servicios ya son errores de
dominio con su código HTTP (400, 413, 501, 503).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, File, UploadFile

from backend.core.config import get_settings
from backend.core.errors import AppError, BadRequestError, NotImplementedFeatureError
from backend.schemas.ai import (
    AIProviderStatus, AIProvidersResponse, AIQueryRequest, AIQueryResponse, TranscriptionResponse, VoiceStatus,
)
from backend.services.ai_agent.llm_providers.provider_factory import MODES, get_provider
from backend.services.ai_agent.nl2sql_agent import NL2SQLAgent
from backend.services.speech.speech_provider import SpeechToTextProvider, get_speech_provider

router = APIRouter(tags=["Asistente IA (NL2SQL)"])

DEFAULT_AUDIO_TYPE = "audio/webm"   # MediaRecorder de Chrome/Edge graba webm/opus


async def _provider_status(mode: str) -> AIProviderStatus:
    """Estado de un modo; un proveedor mal configurado se reporta como no disponible (no como error)."""
    settings = get_settings().ai
    try:
        provider = get_provider(mode, settings)
    except AppError as exc:
        return AIProviderStatus(mode=mode, provider="-", model="-", available=False, detail=exc.message)
    health = await provider.health()
    return AIProviderStatus(**provider.describe(), available=health.available, detail=health.detail)


@router.get("/ai/providers", response_model=AIProvidersResponse)
async def list_providers():
    """Estado de los motores de IA y de la voz, para que la interfaz muestre qué está disponible."""
    settings = get_settings().ai
    # Los health-checks se hacen en paralelo: la pantalla no espera la suma de ambos timeouts
    providers = await asyncio.gather(*(_provider_status(mode) for mode in MODES))
    speech = get_speech_provider()
    return AIProvidersResponse(
        default_mode=settings.default_mode,
        allow_fallback=settings.allow_fallback,
        providers=list(providers),
        voice_enabled=speech is not None,
        voice=VoiceStatus(**speech.status()) if speech else VoiceStatus(enabled=False, detail="VOICE_ENABLED=false"),
    )


@router.post("/ai/query", response_model=AIQueryResponse)
async def ask_assistant(payload: AIQueryRequest):
    """Pregunta en lenguaje natural -> guardrails -> SQL generado por la IA -> datos + respuesta."""
    result = await NL2SQLAgent().ask(payload.question.strip(), payload.mode, payload.summarize)
    return AIQueryResponse(**asdict(result))


@router.post("/query", response_model=AIQueryResponse, include_in_schema=False)
async def ask_assistant_alias(payload: AIQueryRequest):
    """Alias con el nombre de endpoint sugerido en el documento del reto (POST /api/query)."""
    return await ask_assistant(payload)


def _require_speech_provider() -> SpeechToTextProvider:
    provider = get_speech_provider()
    if provider is None:
        raise NotImplementedFeatureError("El reconocimiento de voz está deshabilitado (VOICE_ENABLED=false)")
    return provider


async def _read_audio(audio: UploadFile) -> bytes:
    """Lee el audio subido; un fallo de lectura es un error del cliente (400), no del servidor."""
    try:
        return await audio.read()
    except (OSError, ValueError) as exc:
        raise BadRequestError(f"No se pudo leer el audio enviado: {exc}") from exc
    finally:
        await audio.close()


@router.post("/ai/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio del micrófono (webm/opus, wav, mp3, ogg)"),
):
    """Voz a texto 100 % local con faster-whisper. Solo acepta audio en español."""
    provider = _require_speech_provider()
    result = await provider.transcribe(await _read_audio(audio), audio.content_type or DEFAULT_AUDIO_TYPE)
    return TranscriptionResponse(
        text=result.text, language=result.language, language_probability=result.language_probability,
        duration_seconds=result.duration_seconds, elapsed_ms=result.elapsed_ms,
        model=result.model, device=result.device,
    )


@router.post("/ai/voice", response_model=AIQueryResponse)
async def ask_assistant_by_voice(audio: UploadFile = File(...), mode: str | None = None):
    """Atajo: transcribe el audio y lo envía directamente al asistente."""
    provider = _require_speech_provider()
    transcription = await provider.transcribe(await _read_audio(audio), audio.content_type or DEFAULT_AUDIO_TYPE)
    # "…" hace que una transcripción vacía caiga en el guardrail de pregunta vacía
    return await ask_assistant(AIQueryRequest(question=transcription.text or "…", mode=mode))
