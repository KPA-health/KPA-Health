"""
Configuración centralizada del backend.

Todos los valores se leen de variables de entorno (archivo .env en la raíz del
proyecto). Ningún secreto vive en el código: ver .env.example.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw and raw.strip() else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw and raw.strip() else default


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class LocalAISettings:
    """Modo local: modelo servido en la máquina (Ollama o LM Studio)."""
    provider: str            # "ollama" | "openai_compatible"
    model: str
    ollama_base_url: str
    openai_base_url: str     # LM Studio u otro servidor local compatible con OpenAI
    openai_api_key: str
    keep_alive: str
    num_ctx: int
    think: str               # auto | true | false  (modelos Qwen3 con razonamiento)


@dataclass(frozen=True)
class CloudAISettings:
    """Modo nube: Gemini (por defecto) o cualquier API compatible con OpenAI."""
    provider: str            # "gemini" | "openai_compatible"
    gemini_api_key: str
    gemini_model: str
    gemini_base_url: str
    gemini_thinking_level: str
    openai_base_url: str
    openai_api_key: str
    openai_model: str


@dataclass(frozen=True)
class AISettings:
    default_mode: str        # "local" | "cloud"
    allow_fallback: bool     # si el modo pedido falla, ¿intentar el otro?
    summarize_results: bool  # segunda llamada al LLM para redactar la respuesta
    max_rows: int
    sql_timeout_seconds: float
    max_repair_attempts: int
    llm_timeout_seconds: float
    local: LocalAISettings
    cloud: CloudAISettings


@dataclass(frozen=True)
class VoiceSettings:
    """Voz a texto 100 % local con faster-whisper."""
    enabled: bool
    model_size: str          # tiny | base | small | medium
    device: str              # cpu | cuda | auto
    compute_type: str        # int8 (cpu) | float16 (cuda) | auto
    beam_size: int
    preload: bool            # cargar el modelo en segundo plano al arrancar
    max_seconds: int
    max_mb: int
    min_language_probability: float  # umbral para rechazar audio que no esté en español


@dataclass(frozen=True)
class AuthSettings:
    """Login con JWT y roles (admin | user)."""
    enabled: bool
    jwt_secret: str
    jwt_algorithm: str
    access_token_minutes: int
    admin_username: str
    admin_password: str
    user_username: str
    user_password: str
    max_failed_attempts: int
    lockout_seconds: int
    secret_is_ephemeral: bool = False


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_path: Path
    reference_datetime: str          # "auto" o "YYYY-MM-DD HH:MM:SS"
    privacy_salt: str                # secreto para el hash (HMAC) de documentos de identidad
    cors_origins: list[str] = field(default_factory=list)
    serve_frontend: bool = True
    frontend_dir: Path = PROJECT_ROOT / "hospital-spa"
    max_upload_mb: int = 250
    ai: AISettings | None = None
    voice: VoiceSettings | None = None
    auth: AuthSettings | None = None


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    ai = AISettings(
        default_mode=_env("AI_DEFAULT_MODE", "local").lower(),
        allow_fallback=_env_bool("AI_ALLOW_FALLBACK", False),
        summarize_results=_env_bool("AI_SUMMARIZE_RESULTS", True),
        max_rows=_env_int("AI_MAX_ROWS", 200),
        sql_timeout_seconds=_env_float("AI_SQL_TIMEOUT_SECONDS", 10.0),
        max_repair_attempts=_env_int("AI_MAX_REPAIR_ATTEMPTS", 1),
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 90.0),
        local=LocalAISettings(
            provider=_env("LOCAL_PROVIDER", "ollama").lower(),
            model=_env("LOCAL_MODEL", "qwen3:8b"),
            ollama_base_url=_env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            openai_base_url=_env("LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
            openai_api_key=_env("LOCAL_OPENAI_API_KEY", "lm-studio"),
            keep_alive=_env("OLLAMA_KEEP_ALIVE", "30m"),
            num_ctx=_env_int("OLLAMA_NUM_CTX", 8192),
            think=_env("OLLAMA_THINK", "auto").lower(),
        ),
        cloud=CloudAISettings(
            provider=_env("CLOUD_PROVIDER", "gemini").lower(),
            gemini_api_key=_env("GEMINI_API_KEY"),
            gemini_model=_env("GEMINI_MODEL", "gemini-3.8-flash"),
            gemini_base_url=_env(
                "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
            ).rstrip("/"),
            gemini_thinking_level=_env("GEMINI_THINKING_LEVEL", "low"),
            openai_base_url=_env("CLOUD_OPENAI_BASE_URL").rstrip("/"),
            openai_api_key=_env("CLOUD_OPENAI_API_KEY"),
            openai_model=_env("CLOUD_OPENAI_MODEL"),
        ),
    )

    voice = VoiceSettings(
        enabled=_env_bool("VOICE_ENABLED", True),
        model_size=_env("WHISPER_MODEL", "small"),
        device=_env("WHISPER_DEVICE", "cpu").lower(),
        compute_type=_env("WHISPER_COMPUTE_TYPE", "int8").lower(),
        beam_size=_env_int("WHISPER_BEAM_SIZE", 5),
        preload=_env_bool("WHISPER_PRELOAD", True),
        max_seconds=_env_int("VOICE_MAX_SECONDS", 60),
        max_mb=_env_int("VOICE_MAX_MB", 10),
        min_language_probability=_env_float("VOICE_MIN_LANGUAGE_PROBABILITY", 0.75),
    )

    jwt_secret = _env("JWT_SECRET")
    auth = AuthSettings(
        enabled=_env_bool("AUTH_ENABLED", True),
        # Sin JWT_SECRET se genera uno temporal: los tokens dejan de valer al reiniciar
        jwt_secret=jwt_secret or secrets.token_urlsafe(48),
        secret_is_ephemeral=not jwt_secret,
        jwt_algorithm="HS256",
        access_token_minutes=_env_int("JWT_EXPIRE_MINUTES", 480),
        admin_username=_env("AUTH_ADMIN_USERNAME", "admin"),
        admin_password=_env("AUTH_ADMIN_PASSWORD", "Admin2026*"),
        user_username=_env("AUTH_USER_USERNAME", "usuario"),
        user_password=_env("AUTH_USER_PASSWORD", "Usuario2026*"),
        max_failed_attempts=_env_int("AUTH_MAX_FAILED_ATTEMPTS", 5),
        lockout_seconds=_env_int("AUTH_LOCKOUT_SECONDS", 300),
    )

    origins = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]

    return Settings(
        app_name=_env("APP_NAME", "MediPulse Backend · HSLV"),
        database_path=_resolve_path(_env("DATABASE_PATH", "hospital.db")),
        reference_datetime=_env("REFERENCE_DATETIME", "auto"),
        privacy_salt=_env("PRIVACY_SALT", "kpa-health-hslv-demo-salt-cambiar-en-produccion"),
        cors_origins=origins or ["*"],
        serve_frontend=_env_bool("SERVE_FRONTEND", True),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 250),
        ai=ai,
        voice=voice,
        auth=auth,
    )
