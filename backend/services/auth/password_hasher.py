"""Hash de contraseñas con PBKDF2-HMAC-SHA256 (recomendación OWASP: >= 600.000 iteraciones)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """
    Devuelve 'pbkdf2_sha256$<iteraciones>$<sal>$<hash>'. Guardar el algoritmo y las
    iteraciones junto al hash permite subirlas en el futuro sin invalidar cuentas.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join([ALGORITHM, str(iterations), base64.b64encode(salt).decode(), base64.b64encode(digest).decode()])


def verify_password(password: str, stored: str) -> bool:
    """Compara en tiempo constante (hmac.compare_digest) para no filtrar información por timing."""
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
