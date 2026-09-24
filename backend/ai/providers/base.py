"""
Contrato común de los proveedores de LLM (patrón Strategy).

El motor NL2SQL solo conoce esta interfaz; agregar un proveedor nuevo
(p. ej. otro modelo local o en la nube) es implementar `generate` y `health`
y registrarlo en registry.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """El proveedor respondió con error o con un formato inesperado."""


class ProviderUnavailableError(ProviderError):
    """El proveedor no está configurado o no es alcanzable."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int


@dataclass(frozen=True)
class ProviderHealth:
    available: bool
    detail: str


class LLMProvider(ABC):
    #: "local" o "cloud"
    mode: str
    #: identificador del proveedor ("ollama", "gemini", "openai_compatible")
    name: str
    model: str

    @abstractmethod
    async def generate(
        self, system: str, prompt: str, *, json_mode: bool = True, temperature: float = 0.0,
        schema: dict | None = None,
    ) -> LLMResult:
        """
        Devuelve el texto generado. Si json_mode, el texto debe ser un objeto JSON.
        `schema` (JSON Schema) lo usan los proveedores que soportan decodificación restringida
        (Ollama); los demás lo ignoran y se apoyan en el prompt + json_mode.
        """

    @abstractmethod
    async def health(self) -> ProviderHealth:
        """Comprueba configuración y conectividad sin consumir tokens."""

    def describe(self) -> dict[str, str]:
        return {"mode": self.mode, "provider": self.name, "model": self.model}
