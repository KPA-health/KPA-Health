"""
Proveedor genérico compatible con la API de OpenAI (/v1/chat/completions).

Sirve tanto para modo local (LM Studio, vLLM, llama.cpp server) como para
modo nube (Groq, OpenRouter, OpenAI, etc.) cambiando solo base_url, modelo y key.
"""
from __future__ import annotations

import time

import httpx

from backend.ai.providers.base import (
    LLMProvider, LLMResult, ProviderError, ProviderHealth, ProviderUnavailableError,
)


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, mode: str, base_url: str, model: str, api_key: str, timeout_seconds: float):
        self.mode = mode
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def generate(
        self, system: str, prompt: str, *, json_mode: bool = True, temperature: float = 0.0,
        schema: dict | None = None,
    ) -> LLMResult:
        if not self._base_url or not self.model:
            raise ProviderUnavailableError(f"Proveedor compatible con OpenAI ({self.mode}) sin configurar")
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", headers=self._headers(), json=payload
                )
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(f"No se pudo conectar con {self._base_url}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self._base_url} no respondió en {self._timeout:.0f} s") from exc

        if response.status_code in (401, 403):
            raise ProviderUnavailableError("API key inválida para el proveedor compatible con OpenAI")
        if response.status_code >= 400:
            raise ProviderError(f"El proveedor respondió {response.status_code}: {response.text[:300]}")
        try:
            text = response.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise ProviderError("Respuesta sin contenido del proveedor compatible con OpenAI") from exc
        return LLMResult(
            text=text, provider=self.name, model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health(self) -> ProviderHealth:
        if not self._base_url or not self.model:
            return ProviderHealth(False, "base_url o modelo sin configurar en .env")
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
        except httpx.HTTPError:
            return ProviderHealth(False, f"Sin conexión con {self._base_url}")
        if response.status_code == 200:
            return ProviderHealth(True, f"Servidor compatible con OpenAI activo ({self.model})")
        return ProviderHealth(False, f"{self._base_url} respondió {response.status_code}")
