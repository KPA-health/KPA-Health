"""Modelos base y sobres de respuesta ({data, count, message}) que espera apiClient.js."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Serializa en camelCase (contrato del frontend) y acepta snake_case o camelCase al entrar."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    count: int


class ItemResponse(BaseModel, Generic[T]):
    data: T
    message: str | None = None


class SuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None
