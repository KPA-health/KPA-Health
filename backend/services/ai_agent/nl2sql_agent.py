"""
Agente NL2SQL: convierte una pregunta en español en datos del hospital y una respuesta redactada.

La clase ``NL2SQLAgent`` es una fachada (patrón Facade) sobre guardrails,
proveedores LLM, validación y ejecución de SQL. El controlador solo llama a
``ask()`` y recibe un ``NL2SQLResult`` listo para serializar.

Flujo por pregunta:
 0. Guardrails de ENTRADA (sin LLM): vacía, idioma, inyección, saludo, datos personales, alcance.
 1. Resolver el modo (local | cloud) y obtener el proveedor de la fábrica.
 2. Pedir al LLM un JSON {category, sql, explanation} con el esquema semántico en el prompt.
    Si la categoría no es "hospital" se responde con un mensaje fijo en español.
 3. Validar el SQL (sql_guard) y ejecutarlo en SQLite de solo lectura (sql_executor).
 4. Si falla la validación o la ejecución, devolver el error al LLM y reintentar
    (AI_MAX_REPAIR_ATTEMPTS veces): el modelo corrige su propio SQL.
 5. Enmascarar columnas con apariencia de dato personal (defensa en profundidad).
 6. Redactar la respuesta en lenguaje natural (segunda llamada opcional al LLM).
 7. Guardrails de SALIDA: sin términos técnicos, sin datos personales, cifras verificadas, en español.
 8. Armar el gráfico con código a partir de las filas reales (sin tokens del LLM).
 9. Devolver respuesta + datos con etiquetas legibles + gráfico + SQL exacto (para la vista técnica).
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from starlette.concurrency import run_in_threadpool

from backend.core.config import AISettings, get_settings
from backend.core.errors import AppError, ServiceUnavailableError
from backend.core.privacy import mask_personal_columns
from backend.models.db_connection import closing_connection
from backend.models.semantic_layer import REFERENCE_KEY, get_param
from backend.services.ai_agent import prompts
from backend.services.ai_agent.chart_builder import build_chart
from backend.services.ai_agent.column_labels import humanize
from backend.services.ai_agent.guardrails import messages
from backend.services.ai_agent.guardrails.input_guard import evaluate_input
from backend.services.ai_agent.guardrails.output_guard import deterministic_answer, guard_answer
from backend.services.ai_agent.llm_providers.base import LLMProvider, ProviderError, ProviderUnavailableError
from backend.services.ai_agent.llm_providers.provider_factory import get_provider, other_mode, resolve_mode
from backend.services.ai_agent.sql_executor import QueryResult, SQLExecutionError, execute_readonly
from backend.services.ai_agent.sql_guard import SQLGuardError, clean_sql_text, validate_and_limit

logger = logging.getLogger("medipulse.nl2sql")

# Quién bloqueó la pregunta (campo `blockedBy` del contrato JSON con la SPA)
BLOCKED_BY_INPUT_GUARD = "input_guard"
BLOCKED_BY_MODEL = "model"

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.+?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.IGNORECASE)
_VALID_MODEL_CATEGORIES = set(prompts.MODEL_CATEGORIES)


@dataclass
class NL2SQLResult:
    """Respuesta completa del agente (se serializa como AIQueryResponse)."""
    success: bool
    question: str
    mode: str
    provider: str
    model: str
    answer: str
    explanation: str
    sql: str | None
    category: str = messages.CATEGORY_HOSPITAL
    blocked_by: str | None = None          # None | BLOCKED_BY_INPUT_GUARD | BLOCKED_BY_MODEL
    columns: list[str] = field(default_factory=list)
    column_labels: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    attempts: list[dict[str, str]] = field(default_factory=list)
    timings: dict[str, int] = field(default_factory=dict)
    reference_date: str | None = None
    fallback_used: bool = False
    warnings: list[str] = field(default_factory=list)
    # Contrato de visualización del chat: texto + datos crudos + tipo de gráfico sugerido
    mensaje_texto: str = ""
    datos_grafico: list[dict[str, Any]] = field(default_factory=list)
    tipo_grafico: str | None = None

    def __post_init__(self) -> None:
        self.mensaje_texto = self.mensaje_texto or self.answer


@dataclass(frozen=True)
class LLMOutput:
    """Salida del modelo ya interpretada."""
    sql: str | None
    explanation: str
    category: str = messages.CATEGORY_HOSPITAL


def _normalize_category(raw: Any) -> str:
    """Categoría del modelo en el vocabulario actual; lo desconocido se trata como 'hospital'."""
    category = str(raw or messages.CATEGORY_HOSPITAL).strip().lower()
    category = messages.LEGACY_CATEGORY_ALIASES.get(category, category)
    return category if category in _VALID_MODEL_CATEGORIES else messages.CATEGORY_HOSPITAL


def parse_llm_output(text: str) -> LLMOutput:
    """
    Interpreta la respuesta del modelo. Acepta el JSON pedido y, como red de seguridad
    para modelos que no respetan el formato, un bloque ```sql``` o un SELECT suelto.
    """
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        sql = data.get("sql")
        sql = clean_sql_text(sql) if isinstance(sql, str) and sql.strip().lower() != "null" else None
        # "categoria" se acepta por compatibilidad con la versión anterior del prompt
        category = _normalize_category(data.get("category") or data.get("categoria"))
        return LLMOutput(sql or None, str(data.get("explanation") or "").strip(), category)

    fence = _SQL_FENCE.search(cleaned)
    if fence:
        return LLMOutput(clean_sql_text(fence.group(1)), "")
    match = re.search(r"\b(WITH|SELECT)\b.+", cleaned, re.DOTALL | re.IGNORECASE)
    return LLMOutput(clean_sql_text(match.group(0)) if match else None, "")


def _parse_summary(text: str) -> str:
    """Texto de la respuesta redactada: {"mensaje_texto": ...} (o el texto plano si no es JSON)."""
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned
    if isinstance(data, dict):
        value = data.get("mensaje_texto") or data.get("answer") or data.get("respuesta") or next(iter(data.values()), "")
        return str(value).strip()
    return cleaned


def _load_reference_date() -> str | None:
    """'Hoy' del sistema (fecha del último dato del HIS), que el prompt usa para fechas relativas."""
    with closing_connection() as conn:
        value = get_param(conn, REFERENCE_KEY)
    return value[:10] if value else None


def _limit_hit(sql: str, row_count: int) -> bool:
    """True si el resultado llenó el LIMIT: el total real puede ser mayor ("al menos N")."""
    match = _TRAILING_LIMIT.search(sql or "")
    return bool(match) and row_count >= int(match.group(1))


class NL2SQLAgent:
    """Agente de lenguaje natural a SQL con switch Local/Nube y guardrails."""

    def __init__(self, settings: AISettings | None = None):
        self.settings = settings or get_settings().ai

    async def ask(self, question: str, mode: str | None = None, summarize: bool | None = None) -> NL2SQLResult:
        """
        Responde una pregunta. Solo lanza excepción si el proveedor de IA no está
        disponible (503); cualquier otro resultado, incluido un rechazo, es una
        respuesta válida para el usuario.
        """
        requested_mode = resolve_mode(mode, self.settings)

        # 0. Guardrails de entrada: respuesta inmediata sin gastar GPU ni tokens
        decision = evaluate_input(question)
        if not decision.allowed:
            return self._blocked_result(question, requested_mode, decision.category,
                                        decision.message or messages.FAILED)

        try:
            return await self._answer_with(get_provider(requested_mode, self.settings), question, summarize)
        except ProviderUnavailableError as exc:
            if not self.settings.allow_fallback:
                raise ServiceUnavailableError(str(exc), {"mode": requested_mode}) from exc
            return await self._answer_with_fallback(question, requested_mode, summarize, exc)
        except ProviderError as exc:
            raise ServiceUnavailableError(f"El proveedor de IA falló: {exc}", {"mode": requested_mode}) from exc

    async def _answer_with_fallback(self, question: str, requested_mode: str, summarize: bool | None,
                                    original_error: ProviderUnavailableError) -> NL2SQLResult:
        """Reintenta con el otro modo (solo si AI_ALLOW_FALLBACK=true, porque puede enviar datos a la nube)."""
        logger.warning("Modo %s no disponible (%s); usando respaldo", requested_mode, original_error)
        fallback = get_provider(other_mode(requested_mode), self.settings)
        try:
            result = await self._answer_with(fallback, question, summarize)
        except ProviderUnavailableError as fallback_error:
            raise ServiceUnavailableError(
                f"Ningún proveedor de IA disponible: {original_error} / {fallback_error}"
            ) from fallback_error
        result.fallback_used = True
        result.warnings.append(f"El modo '{requested_mode}' no estaba disponible: {original_error}")
        return result

    def _blocked_result(self, question: str, mode: str, category: str, message: str) -> NL2SQLResult:
        """Respuesta fija para una pregunta bloqueada por los guardrails de entrada."""
        try:
            described = get_provider(mode, self.settings).describe()
        except AppError:
            described = {"mode": mode, "provider": "-", "model": "-"}
        return NL2SQLResult(
            success=True, question=question, mode=mode, provider=described["provider"],
            model=described["model"], answer=message, explanation="", sql=None,
            category=category, blocked_by=BLOCKED_BY_INPUT_GUARD, timings={"totalMs": 0},
        )

    async def _answer_with(self, provider: LLMProvider, question: str, summarize: bool | None) -> NL2SQLResult:
        """Pasos 2-8 del flujo con un proveedor concreto."""
        started = time.perf_counter()
        reference_date = await run_in_threadpool(_load_reference_date)
        timings = {"llmMs": 0, "sqlMs": 0, "summaryMs": 0}
        attempts: list[dict[str, str]] = []
        base = dict(question=question, mode=provider.mode, provider=provider.name,
                    model=provider.model, reference_date=reference_date)

        def finish() -> dict[str, int]:
            timings["totalMs"] = int((time.perf_counter() - started) * 1000)
            return timings

        # 2-4. Generar SQL, validarlo y ejecutarlo (con reparación automática)
        output, result, final_sql = await self._generate_and_execute(
            provider, question, reference_date, timings, attempts
        )
        if output is not None and output.category != messages.CATEGORY_HOSPITAL:
            return NL2SQLResult(
                success=True, sql=None, category=output.category, blocked_by=BLOCKED_BY_MODEL,
                answer=messages.CATEGORY_MESSAGES.get(output.category, messages.OUT_OF_SCOPE),
                explanation=output.explanation, timings=finish(), attempts=attempts, **base,
            )
        if output is not None and not output.sql:
            return NL2SQLResult(
                success=True, sql=None, answer=messages.NO_DATA, explanation=output.explanation,
                timings=finish(), attempts=attempts, **base,
            )
        if result is None or output is None or final_sql is None:
            last_attempt = attempts[-1] if attempts else {"sql": None, "error": "sin respuesta"}
            return NL2SQLResult(
                success=False, sql=last_attempt["sql"], answer=messages.FAILED,
                explanation=output.explanation if output else "", timings=finish(),
                attempts=attempts, **base,
            )

        # 5. Defensa en profundidad: nada con apariencia de dato personal sale en los resultados
        rows, masked_columns = mask_personal_columns(result.columns, result.rows)
        warnings: list[str] = []
        if masked_columns:
            warnings.append(f"Se ocultaron datos personales en: {', '.join(masked_columns)}")
        labels = [humanize(column) for column in result.columns]
        limit_hit = _limit_hit(final_sql, result.row_count)

        # 6-7. Redacción y guardrails de salida
        answer = await self._compose_answer(provider, question, reference_date, labels, rows,
                                            result.row_count, limit_hit, summarize, timings, warnings)

        # 8. Gráfico sin IA: tipo y puntos salen de las filas reales (la pregunta solo da pistas de palabras)
        chart_type, chart_data = build_chart(result.columns, labels, rows, question)

        return NL2SQLResult(
            success=True, sql=final_sql, answer=answer, explanation=output.explanation,
            columns=result.columns, column_labels=labels, rows=rows, row_count=result.row_count,
            truncated=result.row_count >= self.settings.max_rows,
            attempts=attempts, timings=finish(), warnings=warnings,
            tipo_grafico=chart_type, datos_grafico=chart_data, **base,
        )

    async def _generate_and_execute(
        self, provider: LLMProvider, question: str, reference_date: str | None,
        timings: dict[str, int], attempts: list[dict[str, str]],
    ) -> tuple[LLMOutput | None, QueryResult | None, str | None]:
        """
        Bucle generar -> validar -> ejecutar. Devuelve (salida del LLM, resultado, SQL final).

        Termina antes si el modelo clasifica la pregunta fuera de alcance o no genera SQL;
        en ese caso `resultado` es None y la salida explica por qué.
        """
        prompt = prompts.build_question_prompt(question, reference_date)
        system = prompts.build_system_prompt()
        output: LLMOutput | None = None
        for _ in range(1 + max(0, self.settings.max_repair_attempts)):
            llm = await provider.generate(system, prompt, json_mode=True, schema=prompts.NL2SQL_SCHEMA)
            timings["llmMs"] += llm.latency_ms
            output = parse_llm_output(llm.text)
            if output.category != messages.CATEGORY_HOSPITAL or not output.sql:
                return output, None, None
            try:
                final_sql = validate_and_limit(output.sql, self.settings.max_rows)
                result = await run_in_threadpool(execute_readonly, final_sql, self.settings.sql_timeout_seconds)
                timings["sqlMs"] += result.elapsed_ms
                return output, result, final_sql
            except (SQLGuardError, SQLExecutionError) as exc:
                # El error vuelve al modelo como contexto para que corrija su consulta
                attempts.append({"sql": output.sql, "error": str(exc)})
                prompt = prompts.build_repair_prompt(question, reference_date, output.sql, str(exc))
        return output, None, None

    async def _compose_answer(
        self, provider: LLMProvider, question: str, reference_date: str | None, labels: list[str],
        rows: list[list[Any]], row_count: int, limit_hit: bool, summarize: bool | None,
        timings: dict[str, int], warnings: list[str],
    ) -> str:
        """
        Redacta la respuesta. Siempre existe una versión determinista construida con los
        datos; la del LLM solo la reemplaza si supera los guardrails de salida.
        """
        answer = deterministic_answer(labels, rows, row_count, limit_hit)
        should_summarize = self.settings.summarize_results if summarize is None else summarize
        if should_summarize:
            try:
                # Salida JSON: la decodificación restringida impide que un modelo "thinking"
                # anteponga su razonamiento y reduce la latencia (ver ollama_provider.py).
                summary = await provider.generate(
                    prompts.SUMMARY_SYSTEM_PROMPT,
                    prompts.build_summary_prompt(question, reference_date, labels, rows, row_count, limit_hit),
                    json_mode=True, temperature=0.2, schema=prompts.SUMMARY_SCHEMA,
                )
                timings["summaryMs"] = summary.latency_ms
                answer = _parse_summary(summary.text) or answer
            except ProviderError as exc:
                # La redacción es opcional: si falla, se conserva la respuesta determinista
                warnings.append(f"No se pudo redactar la respuesta con IA: {exc}")

        answer, output_warnings = guard_answer(answer, labels, rows, row_count, question,
                                               reference_date, limit_hit)
        warnings.extend(output_warnings)
        return answer
