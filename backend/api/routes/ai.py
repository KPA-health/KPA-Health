"""Asistente IA: NL2SQL con switch Local/Nube, guardrails y voz a texto local (Whisper)."""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, File, UploadFile

from backend.ai.nl2sql.service import NL2SQLService
from backend.ai.providers.registry import MODES, get_provider
from backend.ai.speech.base import get_speech_provider
from backend.core.config import get_settings
from backend.core.errors import AppError, NotImplementedFeatureError
from backend.schemas.ai import (
    AIProviderStatus, AIProvidersResponse, AIQueryRequest, AIQueryResponse, TranscriptionResponse,
    VoiceStatus,
)

router = APIRouter(tags=["Asistente IA (NL2SQL)"])


@router.get("/ai/providers", response_model=AIProvidersResponse)
async def list_providers():
    """Estado de los motores de IA y de la voz para que la interfaz muestre qué está disponible."""
    settings = get_settings().ai

    async def status(mode: str) -> AIProviderStatus:
        try:
            provider = get_provider(mode, settings)
        except AppError as exc:
            return AIProviderStatus(mode=mode, provider="-", model="-", available=False, detail=exc.message)
        health = await provider.health()
        return AIProviderStatus(**provider.describe(), available=health.available, detail=health.detail)

    providers = await asyncio.gather(*(status(mode) for mode in MODES))
    speech = get_speech_provider()
    return AIProvidersResponse(
        default_mode=settings.default_mode,
        allow_fallback=settings.allow_fallback,
        providers=list(providers),
        voice_enabled=speech is not None,
        voice=VoiceStatus(**speech.status()) if speech else VoiceStatus(enabled=False, detail="VOICE_ENABLED=false"),
    )


@router.post("/ai/query", response_model=AIQueryResponse)
async def ai_query(payload: AIQueryRequest):
    """Pregunta en lenguaje natural -> guardrails -> SQL generado por la IA -> datos + respuesta."""
    result = await NL2SQLService().ask(payload.question.strip(), payload.mode, payload.summarize)
    return AIQueryResponse(**asdict(result))


@router.post("/query", response_model=AIQueryResponse, include_in_schema=False)
async def query_alias(payload: AIQueryRequest):
    """Alias con el nombre de endpoint sugerido en el documento del reto (POST /api/query)."""
    return await ai_query(payload)


def _speech_or_501():
    provider = get_speech_provider()
    if provider is None:
        raise NotImplementedFeatureError("El reconocimiento de voz está deshabilitado (VOICE_ENABLED=false)")
    return provider


@router.post("/ai/transcribe", response_model=TranscriptionResponse)
async def transcribe(audio: UploadFile = File(..., description="Audio del micrófono (webm/opus, wav, mp3, ogg)")):
    """Voz a texto 100 % local con faster-whisper. Solo acepta audio en español."""
    provider = _speech_or_501()
    result = await provider.transcribe(await audio.read(), audio.content_type or "audio/webm")
    return TranscriptionResponse(
        text=result.text, language=result.language, language_probability=result.language_probability,
        duration_seconds=result.duration_seconds, elapsed_ms=result.elapsed_ms,
        model=result.model, device=result.device,
    )


@router.post("/ai/voice", response_model=AIQueryResponse)
async def voice_query(audio: UploadFile = File(...), mode: str | None = None):
    """Atajo: transcribe el audio y lo envía directamente al asistente."""
    provider = _speech_or_501()
    transcription = await provider.transcribe(await audio.read(), audio.content_type or "audio/webm")
    return await ai_query(AIQueryRequest(question=transcription.text or "…", mode=mode))
