"""
Factory del switch dinámico Local/Nube.

`get_provider("local")` y `get_provider("cloud")` devuelven la implementación
configurada en .env (LOCAL_PROVIDER / CLOUD_PROVIDER). El modo por petición
lo elige el frontend; si no llega, se usa AI_DEFAULT_MODE.
"""
from __future__ import annotations

from backend.ai.providers.base import LLMProvider
from backend.ai.providers.gemini import GeminiProvider
from backend.ai.providers.ollama import OllamaProvider
from backend.ai.providers.openai_compatible import OpenAICompatibleProvider
from backend.core.config import AISettings, get_settings
from backend.core.errors import ValidationError

MODES = ("local", "cloud")


def resolve_mode(requested: str | None, settings: AISettings | None = None) -> str:
    settings = settings or get_settings().ai
    mode = (requested or settings.default_mode or "local").strip().lower()
    if mode not in MODES:
        raise ValidationError(f"Modo de IA inválido: '{requested}'", {"allowed": list(MODES)})
    return mode


def other_mode(mode: str) -> str:
    return "cloud" if mode == "local" else "local"


def get_provider(mode: str, settings: AISettings | None = None) -> LLMProvider:
    settings = settings or get_settings().ai
    timeout = settings.llm_timeout_seconds

    if mode == "local":
        local = settings.local
        if local.provider == "ollama":
            return OllamaProvider(local, timeout)
        if local.provider in ("openai_compatible", "lmstudio"):
            return OpenAICompatibleProvider(
                "local", local.openai_base_url, local.model, local.openai_api_key, timeout
            )
        raise ValidationError(f"LOCAL_PROVIDER no soportado: {local.provider}")

    cloud = settings.cloud
    if cloud.provider == "gemini":
        return GeminiProvider(cloud, timeout)
    if cloud.provider == "openai_compatible":
        return OpenAICompatibleProvider(
            "cloud", cloud.openai_base_url, cloud.openai_model, cloud.openai_api_key, timeout
        )
    raise ValidationError(f"CLOUD_PROVIDER no soportado: {cloud.provider}")
