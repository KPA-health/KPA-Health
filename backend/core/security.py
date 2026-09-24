"""Cabeceras de seguridad y protección CSRF para sesiones basadas en cookies."""
from __future__ import annotations

import hashlib
import hmac
import base64
from html.parser import HTMLParser

import jwt
from fastapi import Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.config import get_settings
from backend.services.auth.token_service import decode_access_token

SESSION_COOKIE = "medipulse_session"
CSRF_COOKIE = "medipulse_csrf"
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class _InlineInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.handlers = set()
        self.scripts = set()
        self.styles = set()
        self._script = None
        self._style = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for key, value in attrs:
            if key.startswith("on") and value:
                self.handlers.add(value)
        if tag == "script" and "src" not in attributes:
            self._script = []
        if tag == "style":
            self._style = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)
        if self._style is not None:
            self._style.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts.add("".join(self._script))
            self._script = None
        if tag == "style" and self._style is not None:
            self.styles.add("".join(self._style))
            self._style = None


def _hash(value: str) -> str:
    digest = base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()
    return f"'sha256-{digest}'"


def _docs_sources(path: str) -> tuple[str, str]:
    title = get_settings().app_name
    if path == "/docs":
        html = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{title} - Swagger UI",
                                   oauth2_redirect_url="/docs/oauth2-redirect").body.decode()
    elif path == "/redoc":
        html = get_redoc_html(openapi_url="/openapi.json", title=f"{title} - ReDoc").body.decode()
    elif path == "/docs/oauth2-redirect":
        html = get_swagger_ui_oauth2_redirect_html().body.decode()
    else:
        return "", ""
    inventory = _InlineInventory()
    inventory.feed(html)
    return " ".join(map(_hash, sorted(inventory.scripts))), " ".join(map(_hash, sorted(inventory.styles)))


def csrf_token(jwt_token: str) -> str:
    claims = decode_access_token(jwt_token)
    message = f"csrf:{claims['jti']}".encode()
    return hmac.new(get_settings().auth.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (get_settings().auth.enabled and request.method in MUTATING_METHODS
                and request.url.path.startswith(("/api/", "/v1/"))
                and request.url.path not in {"/api/auth/login", "/v1/auth/login"}
                and request.cookies.get(SESSION_COOKIE)
                and not request.headers.get("Authorization", "").lower().startswith("bearer ")):
            try:
                expected = csrf_token(request.cookies[SESSION_COOKIE])
                supplied = request.headers.get("X-CSRF-Token", "")
                cookie = request.cookies.get(CSRF_COOKIE, "")
                valid = hmac.compare_digest(expected, supplied) and hmac.compare_digest(expected, cookie)
            except (jwt.InvalidTokenError, KeyError):
                valid = False
            if not valid:
                return self._headers(JSONResponse(
                    status_code=403,
                    content={"success": False, "message": "Token CSRF inválido o ausente"},
                ), request.url.path)
        return self._headers(await call_next(request), request.url.path)

    @staticmethod
    def _headers(response, path: str):
        # La SPA solo carga scripts locales; Swagger/ReDoc requieren sus hashes de arranque.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        docs_scripts, docs_styles = _docs_sources(path)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; script-src 'self' "
            f"{'https://cdn.jsdelivr.net ' if docs_scripts or path == '/redoc' else ''}{docs_scripts}; "
            f"style-src 'self' https://fonts.googleapis.com "
            f"{'https://cdn.jsdelivr.net ' if path == '/docs' else ''}{docs_styles}; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https://fastapi.tiangolo.com; connect-src 'self'"
        )
        return response
