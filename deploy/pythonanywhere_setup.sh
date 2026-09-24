#!/usr/bin/env bash
# =============================================================================
# Preparación del proyecto en PythonAnywhere (consola Bash de PythonAnywhere).
#
# Uso (desde la carpeta del proyecto clonado):
#     bash deploy/pythonanywhere_setup.sh
#
# Crea el virtualenv "kpa-venv" (en ~/.virtualenvs), instala las dependencias
# livianas de despliegue, crea .env a partir de .env.example y construye hospital.db.
# =============================================================================
set -euo pipefail

VENV_NAME="${VENV_NAME:-kpa-venv}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$HOME/.virtualenvs/$VENV_NAME"

echo "==> Proyecto: $PROJECT_DIR"
echo "==> Creando virtualenv $VENV_DIR con $PYTHON_BIN"
mkdir -p "$HOME/.virtualenvs"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements-deploy.txt"

cd "$PROJECT_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  # En el servidor no hay Ollama ni Whisper: modo nube y voz apagada
  sed -i 's/^AI_DEFAULT_MODE=.*/AI_DEFAULT_MODE=cloud/' .env
  sed -i 's/^VOICE_ENABLED=.*/VOICE_ENABLED=false/' .env
  # Secreto de firma de los JWT generado aleatoriamente
  JWT="$("$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT|" .env
  echo "==> Se creó .env: edítelo (nano .env), ponga su CLOUD_OPENAI_API_KEY y CAMBIE"
  echo "    AUTH_ADMIN_PASSWORD y AUTH_USER_PASSWORD antes del primer arranque"
fi

if [ ! -f hospital.db ]; then
  echo "==> Construyendo hospital.db desde data/ (tarda ~1 minuto)"
  "$VENV_DIR/bin/python" setup_db.py
fi

cat <<INFO

Listo. Siguiente paso (sitio ASGI, beta de PythonAnywhere):

  pip install --user --upgrade pythonanywhere
  pa website create --domain \$USER.pythonanywhere.com \\
     --command '$VENV_DIR/bin/uvicorn --app-dir $PROJECT_DIR --uds \${DOMAIN_SOCKET} backend.main:app'

Para recargar después de cambios:  pa website reload --domain \$USER.pythonanywhere.com
INFO
