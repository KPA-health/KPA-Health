"""Emisión y validación de tokens JWT (HS256)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt

from backend.core.config import get_settings

ISSUER = "kpa-health-hslv"


def create_access_token(username: str, role: str, name: str) -> tuple[str, int]:
    """Devuelve (token, segundos de vigencia)."""
    auth = get_settings().auth
    now = datetime.now(timezone.utc)
    expires = timedelta(minutes=auth.access_token_minutes)
    payload = {
        "sub": username,
        "role": role,
        "name": name,
        "iss": ISSUER,
        "iat": now,
        "exp": now + expires,
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, auth.jwt_secret, algorithm=auth.jwt_algorithm)
    return token, int(expires.total_seconds())


def decode_access_token(token: str) -> dict:
    """Lanza jwt.ExpiredSignatureError o jwt.InvalidTokenError si no es válido."""
    auth = get_settings().auth
    return jwt.decode(
        token, auth.jwt_secret, algorithms=[auth.jwt_algorithm], issuer=ISSUER,
        options={"require": ["exp", "iat", "sub", "role"]},
    )
