"""Proveedor en la nube: Google Gemini (API REST generateContent)."""
from __future__ import annotations

import time

import httpx

from backend.ai.providers.base import (
    LLMProvider, LLMResult, ProviderError, ProviderHealth, ProviderUnavailableError,
)
from backend.core.config import CloudAISettings


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: CloudAISettings, timeout_seconds: float, mode: str = "cloud"):
        self.mode = mode
        self.model = settings.gemini_model
        self._api_key = settings.gemini_api_key
        self._base_url = settings.gemini_base_url
        self._thinking_level = settings.gemini_thinking_level
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ProviderUnavailableError("GEMINI_API_KEY no está configurada en el archivo .env")
        # La API key va en cabecera, nunca en la URL (no queda en logs de proxies)
        return {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

    async def generate(
        self, system: str, prompt: str, *, json_mode: bool = True, temperature: float = 0.0,
        schema: dict | None = None,
    ) -> LLMResult:
        generation_config: dict = {"temperature": temperature}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        if self._thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}

        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        url = f"{self._base_url}/models/{self.model}:generateContent"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError("No hay conexión con la API de Gemini") from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Gemini no respondió en {self._timeout:.0f} s") from exc

        if response.status_code in (401, 403):
            raise ProviderUnavailableError("GEMINI_API_KEY inválida o sin permisos")
        if response.status_code >= 400:
            raise ProviderError(f"Gemini respondió {response.status_code}: {response.text[:300]}")

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as exc:
            reason = data.get("promptFeedback", {}).get("blockReason", "respuesta vacía")
            raise ProviderError(f"Gemini no devolvió contenido ({reason})") from exc
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return LLMResult(
            text=text, provider=self.name, model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health(self) -> ProviderHealth:
        if not self._api_key:
            return ProviderHealth(False, "GEMINI_API_KEY no configurada en .env")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self._base_url}/models/{self.model}", headers=self._headers()
                )
        except httpx.HTTPError:
            return ProviderHealth(False, "Sin conexión con la API de Gemini")
        if response.status_code == 200:
            return ProviderHealth(True, f"Gemini disponible ({self.model})")
        return ProviderHealth(False, f"Gemini respondió {response.status_code} para {self.model}")
