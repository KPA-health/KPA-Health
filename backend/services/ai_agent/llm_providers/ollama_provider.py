"""
Proveedor local: Ollama (qwen3:8b, qwen3:4b u otro modelo descargado).

Razonamiento ("thinking") de Qwen3 — OLLAMA_THINK:
- false: se pide al modelo responder sin razonar (rápido; ideal para Qwen3 híbridos como qwen3:8b).
- true:  el modelo razona y Ollama separa ese razonamiento en `message.thinking`;
         solo se usa `message.content` (la respuesta limpia).
- auto (defecto): se intenta sin razonamiento; si el modelo es de "solo razonamiento"
         (p. ej. qwen3:4b-2507) y aun así mezcla su razonamiento en la respuesta, se
         detecta, se reintenta con think=true y el modelo queda marcado para las
         siguientes llamadas. Las salidas JSON (generación de SQL) usan siempre la
         gramática JSON de Ollama, que impide mezclar texto libre.
"""
from __future__ import annotations

import logging
import time

import httpx

from backend.services.ai_agent.guardrails.output_guard import looks_like_reasoning
from backend.services.ai_agent.llm_providers.base import (
    LLMProvider, LLMResult, ProviderError, ProviderHealth, ProviderUnavailableError,
)
from backend.core.config import LocalAISettings

logger = logging.getLogger("medipulse.ollama")

# Modelos detectados como "solo razonamiento" durante la ejecución (compartido entre instancias)
_THINKING_ONLY_MODELS: set[str] = set()


class OllamaProvider(LLMProvider):
    """Cliente de la API /api/chat de Ollama con manejo adaptativo del modo "thinking"."""

    name = "ollama"

    def __init__(self, settings: LocalAISettings, timeout_seconds: float, mode: str = "local"):
        self.mode = mode
        self.model = settings.model
        self._base_url = settings.ollama_base_url
        # Un túnel protegido con usuario:clave en la URL no debe mostrar la clave en los mensajes
        self._display_url = str(httpx.URL(self._base_url).copy_with(username=None, password=None))
        self._keep_alive = settings.keep_alive
        self._num_ctx = settings.num_ctx
        self._think_mode = settings.think
        self._timeout = timeout_seconds

    def _think_for(self, json_mode: bool) -> bool:
        """Decide si pedir razonamiento: nunca en salidas JSON (la gramática ya las acota)."""
        if self._think_mode == "true":
            return True
        if self._think_mode == "false" or json_mode:
            return False
        return self.model in _THINKING_ONLY_MODELS

    async def _chat(self, system: str, prompt: str, json_mode: bool, temperature: float, think: bool,
                    schema: dict | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": think,
            "keep_alive": self._keep_alive,
            "options": {"temperature": temperature, "num_ctx": self._num_ctx, "seed": 42},
        }
        if schema:
            payload["format"] = schema          # decodificación restringida al esquema exacto
        elif json_mode:
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"No se pudo conectar con Ollama en {self._display_url}. ¿Está corriendo `ollama serve`?"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Ollama no respondió en {self._timeout:.0f} s") from exc

        if response.status_code == 404:
            raise ProviderUnavailableError(
                f"El modelo '{self.model}' no está descargado. Ejecute: ollama pull {self.model}"
            )
        if response.status_code >= 400:
            raise ProviderError(f"Ollama respondió {response.status_code}: {response.text[:300]}")
        return response.json().get("message", {})

    async def generate(
        self, system: str, prompt: str, *, json_mode: bool = True, temperature: float = 0.0,
        schema: dict | None = None,
    ) -> LLMResult:
        started = time.perf_counter()
        think = self._think_for(json_mode)
        message = await self._chat(system, prompt, json_mode, temperature, think, schema)
        content = message.get("content", "")

        if (not think and not json_mode and self._think_mode == "auto"
                and looks_like_reasoning(content)):
            logger.info("'%s' mezcla su razonamiento en la respuesta: se usará think=true", self.model)
            _THINKING_ONLY_MODELS.add(self.model)
            message = await self._chat(system, prompt, json_mode, temperature, True)
            content = message.get("content", "")

        return LLMResult(
            text=content, provider=self.name, model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
        except httpx.HTTPError:
            return ProviderHealth(False, f"Ollama no responde en {self._display_url}")
        models = {m.get("name") for m in response.json().get("models", [])}
        if self.model not in models and f"{self.model}:latest" not in models:
            return ProviderHealth(False, f"Modelo '{self.model}' no descargado (ollama pull {self.model})")
        return ProviderHealth(True, f"Ollama activo con {self.model}")
