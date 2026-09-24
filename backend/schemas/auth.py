"""DTOs de autenticación y administración de usuarios (contrato con authService.js)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.schemas.common import CamelModel


class LoginRequest(CamelModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(CamelModel):
    username: str
    name: str
    role: str
    role_label: str
    permissions: list[str]
    active: bool = True
    last_login: str | None = None


class LoginResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(CamelModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "user"] = "user"
    name: str = Field(default="", max_length=120)


class UserUpdate(CamelModel):
    role: Literal["admin", "user"] | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)
