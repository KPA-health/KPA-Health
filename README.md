# KPA-Health · Asistente IA y Dashboard Hospitalario

**Hospital Susana López de Valencia E.S.E. — Reto Hackathon Campus Party FUP (Ingeniería de Sistemas)**

Plataforma web con un **asistente conversacional (Agente IA NL2SQL)** y un **dashboard de KPIs** que permite a directivos y jefes de servicio consultar en lenguaje natural la operación del hospital: ocupación de camas, tiempos de espera, quirófanos, farmacia e ingresos.

---

## 1. Descripción del reto

El Hospital Susana López de Valencia es una institución de mediana complejidad en proceso de modernización. Atiende en promedio **500 pacientes diarios** en urgencias, hospitalización y consulta externa.

**El problema:** la información sobre ocupación de camas, tiempos de espera, uso de quirófanos, consumo de medicamentos y citas está **dispersa en múltiples sistemas y hojas de cálculo desconectadas** (Historia Clínica, Farmacia, Admisiones). En consecuencia:

- Los directivos dedican horas a pedir reportes a TI o a analizar hojas de cálculo a mano.
- No hay una visión integrada ni en tiempo real de la capacidad hospitalaria, algo crítico en temporadas de alta demanda.
- Se retrasan decisiones para optimizar la capacidad instalada, reducir tiempos de espera y garantizar medicamentos críticos. Esto afecta la calidad de la atención y la eficiencia del gasto en salud.

**Lo que pide el reto:**
- Un MVP con un **agente de IA** que responda preguntas en lenguaje natural.
- Un **dashboard** con KPIs hospitalarios.
- **Carga de datos históricos** (admisiones, camas, quirófanos y farmacia).
- **Recomendaciones y alertas** (desabastecimiento, ocupación alta).
- **Anonimización** de los datos de pacientes.

## 2. Nuestra solución

| Módulo | Qué hace |
|---|---|
| **Dashboard BI** | KPIs reales (ocupación, espera en triaje, quirófanos, stock crítico), tendencia de ocupación, distribución por servicio, capacidad por servicio y censo de urgencias. Filtros por periodo y servicio. |
| **Asistente KPA-Health** | Preguntas en español → SQL generado por IA → respuesta en lenguaje natural. Switch **Local (Ollama/Qwen)** / **Nube (OpenRouter o Gemini)**, dictado por voz con **Whisper local** y vista opcional del SQL generado. Responde solo sobre el hospital, solo en español y nunca expone datos personales. |
| **Gestión de ingresos** | Wizard de admisión (paciente → triaje → cama) que registra el ingreso en la base de datos y actualiza los dashboards al instante. |
| **Gestión de datos** | Carga de los datasets del HIS (pacientes, triage, ingresos, atención, medicamentos, servicios, cirugías) con la misma limpieza del ETL. |
| **Resiliencia** | Si el backend falla o la base de datos está vacía, la app usa datos simulados (`mockData.js`) automáticamente y no se cae durante la demo. |
| **Privacidad** | Los nombres nunca se guardan (seudónimos), las cédulas se guardan cifradas (HMAC) y hay filtros en la API, en la IA y en la interfaz (Habeas Data, Ley 1581 de 2012). |
| **Login y roles** | Inicio de sesión con **JWT**. **admin**: acceso total. **user**: dashboard, asistente IA y gestión de ingresos. El backend aplica los permisos en cada endpoint (403) y la interfaz oculta lo que el rol no puede usar. |

La arquitectura, las decisiones técnicas y los patrones de diseño están documentados en **[`Historial_Arquitectura_Backend.md`](Historial_Arquitectura_Backend.md)**.

```
 VISTA                         CONTROLADOR                 MODELO
 frontend (SPA)  ──HTTP──►  backend/controllers  ──►  backend/models  ──►  SQLite hospital.db
   │ fallback automático            │
   └──► mockData.js                 └──► backend/services
                                         ├── ai_agent/        IA local (Ollama/Qwen3) o nube (OpenRouter/Gemini)
                                         ├── speech/          Voz: faster-whisper (local)
                                         ├── file_processing/ Limpieza e inserción con Pandas
                                         └── auth/            JWT, contraseñas y roles
```

## 3. Estructura del proyecto

```
├── backend/               API FastAPI con arquitectura MVC
│   ├── main.py            Fábrica de la app: middlewares, errores, rutas y SPA estática
│   ├── controllers/       CONTROLADOR: un archivo por recurso (/patients, /rooms, /ai...)
│   ├── models/            MODELO: conexión SQLite, esquema del HIS, capa semántica y entidades
│   ├── schemas/           DTOs Pydantic (contrato JSON con la SPA)
│   ├── services/          Agente IA NL2SQL, Whisper, procesamiento de archivos y autenticación
│   └── core/              Configuración, errores HTTP, privacidad y utilidades
├── frontend/              VISTA: SPA (index.html + js/services, js/views, js/components, app.js)
├── data/                  Datasets del HIS (.txt separados por "|")
├── tests/                 Pruebas automáticas (pytest)
├── deploy/                Script de preparación para PythonAnywhere
├── setup_db.py            CLI de carga inicial: construye hospital.db desde data/
├── requirements.txt       Dependencias completas (desarrollo + voz + pruebas)
├── requirements-deploy.txt Dependencias livianas para servidor
├── .env.example           Plantilla de variables de entorno (copiar a .env)
└── Historial_Arquitectura_Backend.md   Documentación técnica detallada
```

## 4. Instrucciones para ejecutar el proyecto (paso a paso desde cero)

### 4.1 Requisitos

- **Python 3.11 o 3.12** ([python.org](https://www.python.org/downloads/)).
- **Git**.
- **Para el modo nube (recomendado si no tienes GPU):** una API key gratuita de [OpenRouter](https://openrouter.ai) (*Settings → Keys → Create Key*).
- **Para el modo local (opcional):** [Ollama](https://ollama.com/download) y unos 6 GB libres (recomendado: GPU con 8 GB de VRAM).

### 4.2 Clonar e instalar

**Linux / macOS**
```bash
git clone <URL-del-repositorio> KPA-hackaton
cd KPA-hackaton
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
git clone <URL-del-repositorio> KPA-hackaton
cd KPA-hackaton
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
> Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 4.3 Configurar las variables de entorno (`.env`)

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Abre `.env` y elige **al menos un** motor de IA:

- **Solo nube (sin modelo local):** pega tu key de OpenRouter y pon el modo por defecto en nube:
  ```ini
  CLOUD_OPENAI_API_KEY=sk-or-v1-...
  AI_DEFAULT_MODE=cloud
  ```
- **Local (opcional):** instala Ollama y descarga el modelo:
  ```bash
  ollama pull qwen3:8b
  ```
  Con `AI_DEFAULT_MODE=local` (valor por defecto) se usa el modelo local. Si Ollama no está disponible en ese PC, **la interfaz cambia sola al modo nube**.

> 🔒 `.env` contiene credenciales: **nunca lo subas al repositorio** (ya está en `.gitignore`). Comparte solo `.env.example`.

### 4.4 Construir la base de datos

```bash
python setup_db.py
```
Lee los archivos de `data/`, los limpia y anonimiza, y crea `hospital.db` (~1 minuto). Al arrancar, el backend agrega la capa semántica (vistas, KPIs e inventario).

### 4.5 Usuarios y roles

Al arrancar por primera vez, el backend crea dos usuarios con los valores de `.env`:

| Usuario | Contraseña por defecto | Rol | Acceso |
|---|---|---|---|
| `admin` | `Admin2026*` | Administrador | Todo: dashboard, asistente, ingresos, gestión de datos, configuración de la API y usuarios |
| `usuario` | `Usuario2026*` | Usuario | Dashboard, asistente IA y gestión de ingresos |

> 🔒 Cambia `AUTH_ADMIN_PASSWORD`, `AUTH_USER_PASSWORD` y define un `JWT_SECRET` propio en `.env` **antes** del primer arranque (los usuarios se crean una sola vez). Genera el secreto con:
> `python -c "import secrets; print(secrets.token_urlsafe(48))"`

Un administrador puede crear más usuarios desde la API (`POST /api/auth/users`, ver `/docs`). Para demos sin login: `AUTH_ENABLED=false`.

### 4.6 Ejecutar

```bash
uvicorn backend.main:app --port 8000
```
Espera la línea `Application startup complete` y abre:

| URL | Qué es |
|---|---|
| http://localhost:8000/ | La aplicación completa (dashboard, asistente, ingresos, datos) |
| http://localhost:8000/docs | Documentación interactiva de la API (Swagger) |

Para detener el servidor: `Ctrl + C`. Para desarrollar con recarga automática: `uvicorn backend.main:app --reload --port 8000`.

### 4.7 Probar

0. **Login:** entra con `usuario` y verifica que solo ves Dashboard, Asistente e Ingresos. Cierra sesión y entra con `admin`: aparecen también Gestión de Datos y Configuración API.
1. **Dashboard BI:** revisa los KPIs y cambia los filtros (*Hoy / Últimos 7 días / Último mes*, servicio).
2. **Asistente IA:** toca una consulta rápida, p. ej. *"¿Cuántas camas de UCI están ocupadas hoy?"*. Activa **Detalle técnico** para ver el SQL generado. Prueba el micrófono 🎤 (solo funciona en `localhost` o HTTPS).
3. **Gestión de ingresos:** registra un paciente y vuelve al dashboard: el ingreso ya aparece contado.
4. **Gestión de datos:** sube un archivo de `data/` y observa los registros insertados.
5. **Modo respaldo:** detén el backend y recarga la página: la app sigue funcionando con datos simulados.

**Pruebas automáticas** (usan una base temporal y un LLM simulado: no necesitan Ollama ni API keys):
```bash
python -m pytest
```

### 4.8 Opciones útiles

| Variable (`.env`) | Para qué |
|---|---|
| `AI_DEFAULT_MODE` | `local` o `cloud`: motor usado por defecto |
| `LOCAL_MODEL` | Modelo de Ollama (recomendado `qwen3:8b`; `qwen3:4b` para equipos con poca VRAM) |
| `CLOUD_PROVIDER` | `openai_compatible` (OpenRouter, Groq…) o `gemini` |
| `VOICE_ENABLED` | `false` si no quieres usar Whisper (la primera vez descarga ~460 MB) |
| `AI_SUMMARIZE_RESULTS` | `false` para respuestas más rápidas sin redacción por IA |
| `PRIVACY_SALT` | Secreto del cifrado de documentos: **cámbialo en producción** |
| `AUTH_ENABLED` | `false` para desactivar el login (acceso libre como administrador) |
| `JWT_SECRET` / `JWT_EXPIRE_MINUTES` | Secreto de firma y duración de la sesión |

En el frontend, `frontend/js/config.js` tiene los *feature flags* `ENABLE_VOICE_INPUT` (mostrar u ocultar el micrófono) y `VOICE_AUTO_SUBMIT`.

## 5. Despliegue en PythonAnywhere

FastAPI es una app ASGI; PythonAnywhere la soporta mediante su función de **sitios ASGI (beta)**. En el servidor no hay Ollama ni GPU, así que se usa el **modo nube** con la voz desactivada.

1. En una **consola Bash** de PythonAnywhere:
   ```bash
   git clone <URL-del-repositorio> KPA-hackaton
   cd KPA-hackaton
   bash deploy/pythonanywhere_setup.sh
   ```
   El script:
   - Crea el virtualenv `~/.virtualenvs/kpa-venv` con `requirements-deploy.txt` (sin Whisper).
   - Crea `.env` con `AI_DEFAULT_MODE=cloud` y `VOICE_ENABLED=false`.
   - Construye `hospital.db`.
2. Edita `.env` (`nano .env`): pon tu `CLOUD_OPENAI_API_KEY`, un `JWT_SECRET` propio y cambia las contraseñas `AUTH_ADMIN_PASSWORD` y `AUTH_USER_PASSWORD`.
3. Crea el sitio con el comando que imprime el script:
   ```bash
   pip install --user --upgrade pythonanywhere
   pa website create --domain $USER.pythonanywhere.com \
     --command '/home/'$USER'/.virtualenvs/kpa-venv/bin/uvicorn --app-dir /home/'$USER'/KPA-hackaton --uds ${DOMAIN_SOCKET} backend.main:app'
   ```
4. Abre `https://<usuario>.pythonanywhere.com/`.

> ⚠️ **Antes de desplegar, verifica en la documentación de PythonAnywhere:**
> - **Disco:** `data/` (~190 MB) más `hospital.db` (~280 MB) más el virtualenv superan la cuota del plan gratuito (512 MB). Se necesita un plan de pago o reducir los datos.
> - **Salida a internet:** las cuentas gratuitas solo pueden llamar a dominios de una lista permitida. Confirma que `openrouter.ai` o `generativelanguage.googleapis.com` estén incluidos.
> - Los sitios ASGI están en beta y los comandos pueden cambiar.

## 6. Despliegue en Streamlit Community Cloud

La carpeta `streamlit_app/` contiene una interfaz en Streamlit (asistente IA, dashboard y alertas) que usa el backend directamente, sin la API HTTP ni la SPA. El switch **Local/Nube** se mantiene: la barra lateral muestra qué modo responde y, si el modo por defecto no está disponible, preselecciona el otro.

1. Sube el repositorio a GitHub. `hospital.db` y los secretos no se suben; la base se construye sola desde `data/` en el primer arranque (unos 20 s y ~900 MB de RAM).
2. En [share.streamlit.io](https://share.streamlit.io) → **Create app**:
   - **Main file path:** `streamlit_app/app.py` (las dependencias se toman de `streamlit_app/requirements.txt`).
   - **Advanced settings → Python:** 3.11 o 3.12 (pandas 3 no funciona con versiones anteriores).
   - **Secrets:** pega el contenido de `streamlit_app/secrets.toml.example` con tus valores. Las contraseñas deben tener **8 caracteres o más**; si no, no se crean los usuarios.
3. **Modo nube (OpenAI):** `CLOUD_OPENAI_BASE_URL=https://api.openai.com/v1`, `CLOUD_OPENAI_API_KEY` y `CLOUD_OPENAI_MODEL`. También sirve OpenRouter o Groq cambiando la URL y el modelo.
4. **Modo local (Ollama):** Streamlit Cloud no puede ejecutar el modelo (sin GPU y con ~2.7 GB de RAM). Se sigue usando el Ollama de tu equipo, expuesto con un túnel protegido con contraseña:
   ```bash
   ollama serve
   ngrok http 11434 --host-header="localhost:11434" --basic-auth "kpa:una-clave-larga"
   ```
   Y en los secrets: `OLLAMA_BASE_URL = "https://kpa:una-clave-larga@<subdominio>.ngrok-free.app"`. La clave viaja como Basic Auth y no se muestra en la interfaz. El modo local solo funciona mientras tu equipo y el túnel estén encendidos; las preguntas y resultados viajan hasta tu equipo.

> ⚠️ En Streamlit Cloud el disco es temporal: al reiniciar o redesplegar se reconstruye `hospital.db` desde `data/`, y se pierden los usuarios creados desde la app y las cargas de archivos. La voz (Whisper) queda desactivada.

Para probarlo en local: `pip install streamlit` y `streamlit run streamlit_app/app.py` (usa tu `.env`).

## 7. Tecnologías utilizadas

**Backend**
- Python 3.11 · **FastAPI** · Uvicorn · Pydantic v2 · python-dotenv · python-multipart
- **SQLite** (modo WAL, vistas, tablas materializadas, columnas generadas)
- **pandas** (ETL y limpieza de datasets)
- **sqlglot** (validación del SQL generado por IA) y `sqlite3.set_authorizer` (segunda barrera de seguridad)
- **httpx** (clientes de los proveedores de IA)
- **PyJWT** (tokens de sesión HS256) y **PBKDF2-SHA256** (hash de contraseñas, biblioteca estándar)
- **pytest** (82 pruebas automáticas)

**Inteligencia artificial**
- **Ollama** + **Qwen3** (`qwen3:8b` / `qwen3:4b`): modo local, privado y gratuito
- **OpenRouter** (API compatible con OpenAI, modelos gratuitos) y **Google Gemini**: modo nube
- **faster-whisper** (modelo `small`, CTranslate2, CPU int8): voz a texto 100 % local
- NL2SQL con capa semántica, few-shot, JSON Schema, autocorrección y guardrails de entrada y salida

**Frontend**
- HTML5 · **Tailwind CSS** · JavaScript (SPA modular sin frameworks)
- **Chart.js** (gráficos) · **Lucide** (íconos) · MediaRecorder API (micrófono)

**Herramientas**
- Git / GitHub · Swagger (OpenAPI) · PythonAnywhere (despliegue)

## 8. Roles del equipo y autores

| Integrante | Rol | Aportes |
|---|---|---|
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

## 9. Seguridad y privacidad

- Las credenciales van solo en `.env`, que nunca se sube (`.gitignore`).
- Login con JWT firmado (HS256) y control de acceso por roles en cada endpoint. Las contraseñas se guardan con PBKDF2-SHA256 (600.000 iteraciones) y hay bloqueo temporal tras 5 intentos fallidos.
- Los nombres de pacientes se anonimizan en el ETL y en cada registro nuevo (`Paciente_<id>`). Los documentos se guardan solo como hash HMAC-SHA256.
- El asistente no puede consultar ni devolver nombres, documentos, teléfonos ni texto clínico libre. Esto se aplica en el catálogo del agente, el validador SQL, el authorizer de SQLite, los guardrails de salida y el filtro de la interfaz.
- El SQL generado por la IA se ejecuta en modo de solo lectura, con límite de filas y de tiempo.
- El navegador recibe una CSP restrictiva: JavaScript y CSS se sirven localmente y los eventos de la interfaz se registran desde JavaScript, sin manejadores inline. Swagger y ReDoc solo permiten hashes exactos de sus bloques de arranque. El CSS se regenera con `npm install` y `npm run build:css` después de cambiar clases de Tailwind.
- El JWT del navegador se guarda en una cookie `HttpOnly`, `Secure` y `SameSite=Strict`; las peticiones que cambian datos desde esa sesión requieren `X-CSRF-Token`. Los clientes API que usan `Authorization: Bearer` mantienen el contrato anterior. En producción, sirva la aplicación por HTTPS y desde el mismo origen que la API.
- Las cargas `.txt`/`.csv` validan nombre, MIME y tamaño antes de procesarse en un directorio temporal aislado. Los formularios limitan longitud y caracteres; los valores del SQL generado por IA se enlazan como parámetros de SQLite.
