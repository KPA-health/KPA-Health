"""
Factory del switch dinámico Local/Nube.

`get_provider("local")` y `get_provider("cloud")` devuelven la implementación
configurada en .env (LOCAL_PROVIDER / CLOUD_PROVIDER). El modo por petición
lo elige el frontend; si no llega, se usa AI_DEFAULT_MODE.
"""
from __future__ import annotations

from backend.core.config import AISettings, get_settings
from backend.core.errors import BadRequestError
from backend.services.ai_agent.llm_providers.base import LLMProvider
from backend.services.ai_agent.llm_providers.gemini_provider import GeminiProvider
from backend.services.ai_agent.llm_providers.ollama_provider import OllamaProvider
from backend.services.ai_agent.llm_providers.openai_compatible_provider import OpenAICompatibleProvider

LOCAL_MODE = "local"
CLOUD_MODE = "cloud"
MODES = (LOCAL_MODE, CLOUD_MODE)


def resolve_mode(requested: str | None, settings: AISettings | None = None) -> str:
    """Modo pedido por la interfaz o, si no llega, AI_DEFAULT_MODE; 400 si no es válido."""
    settings = settings or get_settings().ai
    mode = (requested or settings.default_mode or LOCAL_MODE).strip().lower()
    if mode not in MODES:
        raise BadRequestError(f"Modo de IA inválido: '{requested}'", {"allowed": list(MODES)})
    return mode


def other_mode(mode: str) -> str:
    """Modo alternativo para el respaldo automático (AI_ALLOW_FALLBACK)."""
    return CLOUD_MODE if mode == LOCAL_MODE else LOCAL_MODE


def get_provider(mode: str, settings: AISettings | None = None) -> LLMProvider:
    """Fábrica: instancia el proveedor configurado en .env para el modo pedido."""
    settings = settings or get_settings().ai
    timeout = settings.llm_timeout_seconds

    if mode == LOCAL_MODE:
        local = settings.local
        if local.provider == "ollama":
            return OllamaProvider(local, timeout)
        if local.provider in ("openai_compatible", "lmstudio"):
            return OpenAICompatibleProvider(
                LOCAL_MODE, local.openai_base_url, local.model, local.openai_api_key, timeout
            )
        raise BadRequestError(f"LOCAL_PROVIDER no soportado: {local.provider}")

    cloud = settings.cloud
    if cloud.provider == "gemini":
        return GeminiProvider(cloud, timeout)
    if cloud.provider == "openai_compatible":
        return OpenAICompatibleProvider(
            CLOUD_MODE, cloud.openai_base_url, cloud.openai_model, cloud.openai_api_key, timeout
        )
    raise BadRequestError(f"CLOUD_PROVIDER no soportado: {cloud.provider}")
