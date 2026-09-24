"""
Interfaz Streamlit de KPA-Health (para Streamlit Community Cloud).

    streamlit run streamlit_app/app.py

Reutiliza el backend directamente (sin HTTP): login, dashboard BI, alertas y el
asistente NL2SQL con el switch Local/Nube. La configuración se lee de las mismas
variables que el .env; en Streamlit Cloud se definen en *App settings → Secrets*
(ver streamlit_app/secrets.toml.example).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _export_secrets_to_env() -> None:
    """Copia los secrets de primer nivel al entorno ANTES de que el backend lea su configuración."""
    try:
        secrets = dict(st.secrets)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return  # en local sin secrets.toml se usa el .env
    for key, value in secrets.items():
        if not isinstance(value, dict):
            os.environ.setdefault(key, str(value).lower() if isinstance(value, bool) else str(value))


st.set_page_config(page_title="KPA-Health · HSLV", page_icon="🏥", layout="wide")
_export_secrets_to_env()

from backend.core.config import get_settings  # noqa: E402  (después de exportar los secrets)
from backend.core.errors import AppError  # noqa: E402
from backend.models import dashboard_model  # noqa: E402
from backend.models.db_connection import closing_connection, enable_wal  # noqa: E402
from backend.models.semantic_layer import ensure_semantic_layer  # noqa: E402
from backend.models.user_model import ensure_users  # noqa: E402
from backend.services.ai_agent.llm_providers.provider_factory import (  # noqa: E402
    CLOUD_MODE, LOCAL_MODE, get_provider,
)
from backend.services.ai_agent.nl2sql_agent import NL2SQLAgent  # noqa: E402
from backend.services.auth import auth_service  # noqa: E402
from backend.services.auth.permissions import PERM_ASSISTANT, PERM_DASHBOARD, has_permission  # noqa: E402
from backend.services.insights import insights_service  # noqa: E402

MODE_LABELS = {LOCAL_MODE: "Local (Ollama / Qwen)", CLOUD_MODE: "Nube (API compatible con OpenAI)"}
PERIOD_LABELS = {"today": "Hoy", "7d": "Últimos 7 días", "30d": "Últimos 30 días"}
SEVERITY_ICONS = {"alta": "🔴", "media": "🟠", "baja": "🟢"}


# ------------------------------------------------------------------ Arranque
@st.cache_resource(show_spinner="Preparando la base de datos del hospital (solo la primera vez, ~1-2 min)...")
def prepare_database() -> dict:
    """Construye hospital.db desde data/ si no existe y deja lista la capa semántica y los usuarios."""
    settings = get_settings()
    if not settings.database_path.exists():
        import setup_db  # noqa: PLC0415  (script de la raíz del proyecto)
        if setup_db.main() != 0:
            raise RuntimeError("No se pudo construir hospital.db a partir de data/")
    enable_wal()
    with closing_connection() as conn:
        info = ensure_semantic_layer(conn)
        ensure_users(conn)
    return info


@st.cache_data(ttl=60, show_spinner=False)
def provider_status(mode: str) -> tuple[bool, str, str]:
    """(disponible, modelo, detalle) de un modo de IA; se refresca cada minuto."""
    try:
        provider = get_provider(mode)
    except AppError as exc:
        return False, "-", exc.message
    health = asyncio.run(provider.health())
    return health.available, provider.model, health.detail


def run_async(coro):
    """Streamlit ejecuta el script de forma síncrona: cada llamada async usa su propio event loop."""
    return asyncio.run(coro)


# --------------------------------------------------------------------- Login
def login_form() -> None:
    st.title("🏥 KPA-Health")
    st.caption("Hospital Susana López de Valencia E.S.E. · Popayán")
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", type="primary")
    if submitted:
        try:
            with closing_connection() as conn:
                result = auth_service.login(conn, username, password)
        except AppError as exc:
            st.error(exc.message)
        else:
            st.session_state.user = result["user"]
            st.rerun()


def current_user() -> dict | None:
    if not get_settings().auth.enabled:
        return {"username": "demo", "name": "Acceso libre", "role": "admin", "roleLabel": "Administrador"}
    return st.session_state.get("user")


# ------------------------------------------------------------------- Sidebar
def sidebar(user: dict) -> str:
    """Muestra usuario y estado de la IA; devuelve el modo elegido (local | cloud)."""
    with st.sidebar:
        st.markdown(f"**{user['name']}**  \n{user['roleLabel']}")
        if get_settings().auth.enabled and st.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()

        st.divider()
        st.subheader("Motor de IA")
        statuses = {mode: provider_status(mode) for mode in (LOCAL_MODE, CLOUD_MODE)}
        available = [mode for mode, (ok, _, _) in statuses.items() if ok]
        default = get_settings().ai.default_mode
        # Si el modo por defecto no responde, se preselecciona el que sí esté disponible
        preferred = default if default in available else (available[0] if available else default)
        mode = st.radio(
            "Modo", (LOCAL_MODE, CLOUD_MODE), index=(LOCAL_MODE, CLOUD_MODE).index(preferred),
            format_func=lambda m: f"{'🟢' if statuses[m][0] else '🔴'} {MODE_LABELS[m]}",
        )
        ok, model, detail = statuses[mode]
        st.caption(f"Modelo: `{model}`  \n{detail}")
        if st.button("Reintentar conexión"):
            provider_status.clear()
            st.rerun()
    return mode


# ----------------------------------------------------------------- Dashboard
def page_dashboard() -> None:
    st.header("Dashboard hospitalario")
    col_period, col_service = st.columns(2)
    period = col_period.selectbox("Periodo", list(PERIOD_LABELS), format_func=PERIOD_LABELS.get)
    with closing_connection() as conn:
        services = dashboard_model.list_services(conn)
    service = col_service.selectbox("Servicio", ["all", *services],
                                    format_func=lambda s: "Todos" if s == "all" else s)
    with closing_connection() as conn:
        data = dashboard_model.get_dashboard(conn, period, service)
    k = data["kpis"]
    st.caption(f"Datos al {data['referenceDate']} · {data['periodLabel']}")

    c = st.columns(4)
    c[0].metric("Ocupación de camas", f"{k['occupancyRate']} %", f"{k['occupiedBeds']}/{k['totalBeds']} camas",
                delta_color="off")
    c[1].metric("Espera promedio urgencias", f"{k['avgWaitMinutes'] or 0} min", f"{k['waitPatients']} pacientes",
                delta_color="off")
    c[2].metric("Ingresos del periodo", k["admissions"])
    c[3].metric("Pacientes activos", k["activePatients"], f"{k['criticalPatients']} críticos", delta_color="off")
    c = st.columns(4)
    c[0].metric("Cirugías realizadas", f"{k['surgeriesPerformed']}/{k['surgeriesScheduled']}")
    c[1].metric("Medicamentos críticos", k["criticalMeds"], f"{k['lowStockMeds']} en stock bajo", delta_color="off")
    c[2].metric("Estancia promedio", f"{k['avgLengthOfStayDays'] or 0} días")
    c[3].metric("Giro cama", k["bedTurnover"] or 0)

    left, right = st.columns(2)
    trend = data["occupancyTrend"]
    left.subheader("Ocupación diaria (%)")
    left.line_chart(pd.DataFrame({"Ocupación %": trend["occupancyPct"]}, index=trend["dates"]))
    dist = data["serviceDistribution"]
    right.subheader("Ingresos por servicio")
    right.bar_chart(pd.DataFrame({"Ingresos": dist["values"]}, index=dist["labels"]))

    left, right = st.columns(2)
    if data["waitByTriage"]:
        left.subheader("Espera por nivel de triage (min)")
        triage = pd.DataFrame(data["waitByTriage"])
        left.bar_chart(triage.set_index(triage["level"].map(lambda n: f"Nivel {n}"))["avgMinutes"])
    if data["criticalMeds"]:
        right.subheader("Stock crítico de farmacia")
        right.dataframe(pd.DataFrame(data["criticalMeds"]), hide_index=True, width="stretch")


# -------------------------------------------------------------------- Alertas
def page_alerts() -> None:
    st.header("Alertas y recomendaciones")
    with st.spinner("Analizando los datos..."), closing_connection() as conn:
        briefing = insights_service.build_briefing(conn)
    st.info(briefing["headline"])
    for item in briefing["items"]:
        with st.expander(f"{SEVERITY_ICONS.get(item['severity'], '⚪')} {item['title']}"):
            st.write(item["message"])
            if item.get("action"):
                st.markdown(f"**Acción recomendada:** {item['action']}")
            if item.get("items"):
                st.dataframe(pd.DataFrame(item["items"]), hide_index=True, width="stretch")


# ---------------------------------------------------------------- Asistente IA
def render_chart(kind: str | None, points: list[dict]) -> None:
    """Dibuja el gráfico que el backend decidió (bar | line | pie | gauge) con los datos reales."""
    if not kind or not points:
        return
    frame = pd.DataFrame(points)
    if kind == "gauge":
        value = float(frame.iloc[0]["Valor"])
        st.metric(str(frame.iloc[0]["etiqueta"]), f"{value:.1f} %")
        st.progress(min(max(value / 100, 0.0), 1.0))
    elif kind == "pie":
        series = [c for c in frame.columns if c != "etiqueta"][0]
        st.altair_chart(alt.Chart(frame).mark_arc(innerRadius=50).encode(
            theta=f"{series}:Q", color=alt.Color("etiqueta:N", title=None), tooltip=["etiqueta", series]))
    elif kind == "line":
        st.line_chart(frame.set_index("etiqueta"))
    else:
        st.bar_chart(frame.set_index("etiqueta"))


def render_answer(result: dict) -> None:
    st.markdown(result["answer"])
    if result.get("fallback_used"):
        st.caption("⚠️ El modo elegido no respondió: se usó el otro modo (AI_ALLOW_FALLBACK).")
    render_chart(result.get("tipo_grafico"), result.get("datos_grafico") or [])
    if result.get("rows"):
        with st.expander(f"Datos ({result['row_count']} filas{', truncado' if result.get('truncated') else ''})"):
            st.dataframe(pd.DataFrame(result["rows"], columns=result["column_labels"] or result["columns"]),
                         hide_index=True, width="stretch")
    if result.get("sql"):
        with st.expander("Vista técnica (SQL)"):
            st.code(result["sql"], language="sql")
            st.caption(f"{result['provider']} · {result['model']} · {result.get('timings', {}).get('totalMs', '-')} ms")


def page_assistant(mode: str) -> None:
    st.header("Asistente IA")
    st.caption("Pregunte en español sobre ocupación, urgencias, cirugías, farmacia o ingresos.")
    history: list[dict] = st.session_state.setdefault("chat", [])
    for message in history:
        with st.chat_message(message["role"]):
            render_answer(message["result"]) if message["role"] == "assistant" else st.markdown(message["text"])

    question = st.chat_input("Ej.: ¿Cuál es la ocupación por servicio hoy?")
    if not question:
        return
    history.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner(f"Consultando ({MODE_LABELS[mode]})..."):
            try:
                result = run_async(NL2SQLAgent().ask(question, mode))
            except AppError as exc:
                st.error(exc.message)
                return
        payload = vars(result)
        render_answer(payload)
    history.append({"role": "assistant", "result": payload})


# ---------------------------------------------------------------------- Main
def main() -> None:
    try:
        prepare_database()
    except Exception as exc:  # noqa: BLE001  (se muestra en pantalla en vez de un traceback)
        st.error(f"No se pudo preparar la base de datos: {exc}")
        st.stop()

    user = current_user()
    if user is None:
        login_form()
        return

    mode = sidebar(user)
    pages = []
    if has_permission(user["role"], PERM_ASSISTANT):
        pages.append(st.Page(lambda: page_assistant(mode), title="Asistente IA", icon="💬",
                             url_path="asistente", default=True))
    if has_permission(user["role"], PERM_DASHBOARD):
        pages.append(st.Page(page_dashboard, title="Dashboard", icon="📊", url_path="dashboard"))
        pages.append(st.Page(page_alerts, title="Alertas", icon="🚨", url_path="alertas"))
    st.navigation(pages).run()


main()
