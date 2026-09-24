"""
Orquestador del motor NL2SQL (patrón Facade sobre guardrails, proveedores LLM y ejecución).

Flujo por pregunta:
 0. Guardrails de ENTRADA (sin LLM): vacía, idioma, saludo, datos personales, alcance.
 1. Resolver el modo (local | cloud) y obtener el proveedor del registry.
 2. Pedir al LLM un JSON {categoria, sql, explanation} con el esquema semántico en el prompt.
    Si la categoría no es "hospital" se responde con un mensaje fijo en español.
 3. Validar el SQL (sql_guard) y ejecutarlo en SQLite de solo lectura (executor).
 4. Si falla la validación o la ejecución, devolver el error al LLM y reintentar
    (AI_MAX_REPAIR_ATTEMPTS veces).
 5. Enmascarar columnas con apariencia de dato personal (defensa en profundidad).
 6. Redactar la respuesta en lenguaje natural (segunda llamada opcional al LLM).
 7. Guardrails de SALIDA: sin términos técnicos, sin datos personales, en español.
 8. Devolver respuesta + datos con etiquetas legibles + SQL exacto (para la vista técnica).
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from starlette.concurrency import run_in_threadpool

from backend.ai.guardrails import messages
from backend.ai.guardrails.input_guard import evaluate_input
from backend.ai.guardrails.output_guard import deterministic_answer, guard_answer
from backend.ai.nl2sql import prompts
from backend.ai.nl2sql.executor import QueryResult, SQLExecutionError, execute_readonly
from backend.ai.nl2sql.labels import humanize
from backend.ai.nl2sql.sql_guard import SQLGuardError, clean_sql_text, validate_and_limit
from backend.ai.providers.base import LLMProvider, ProviderError, ProviderUnavailableError
from backend.ai.providers.registry import get_provider, other_mode, resolve_mode
from backend.core.config import AISettings, get_settings
from backend.core.database import closing_connection
from backend.core.errors import AppError, ServiceUnavailableError
from backend.core.privacy import mask_personal_columns
from backend.db.semantic_layer import REFERENCE_KEY, get_param

logger = logging.getLogger("medipulse.nl2sql")

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.+?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.IGNORECASE)
_VALID_CATEGORIES = {
    messages.CATEGORY_HOSPITAL, messages.CATEGORY_OUT_OF_SCOPE,
    messages.CATEGORY_LANGUAGE, messages.CATEGORY_PERSONAL_DATA,
}


@dataclass
class NL2SQLResult:
    success: bool
    question: str
    mode: str
    provider: str
    model: str
    answer: str
    explanation: str
    sql: str | None
    category: str = messages.CATEGORY_HOSPITAL
    blocked_by: str | None = None          # None | "entrada" | "modelo"
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


@dataclass(frozen=True)
class _LLMOutput:
    sql: str | None
    explanation: str
    category: str = messages.CATEGORY_HOSPITAL


def parse_llm_output(text: str) -> _LLMOutput:
    """Acepta el JSON pedido y, como red de seguridad, un bloque ```sql``` o un SELECT suelto."""
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            sql = data.get("sql")
            sql = clean_sql_text(sql) if isinstance(sql, str) and sql.strip().lower() != "null" else None
            category = str(data.get("categoria") or data.get("category") or messages.CATEGORY_HOSPITAL)
            category = category.strip().lower()
            if category not in _VALID_CATEGORIES:
                category = messages.CATEGORY_HOSPITAL
            return _LLMOutput(sql or None, str(data.get("explanation") or "").strip(), category)
    except json.JSONDecodeError:
        pass
    fence = _SQL_FENCE.search(cleaned)
    if fence:
        return _LLMOutput(clean_sql_text(fence.group(1)), "")
    match = re.search(r"\b(WITH|SELECT)\b.+", cleaned, re.DOTALL | re.IGNORECASE)
    return _LLMOutput(clean_sql_text(match.group(0)) if match else None, "")


def _reference_date() -> str | None:
    with closing_connection() as conn:
        value = get_param(conn, REFERENCE_KEY)
    return value[:10] if value else None


def _parse_summary(text: str) -> str:
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            value = data.get("respuesta") or data.get("answer") or next(iter(data.values()), "")
            return str(value).strip()
    except (json.JSONDecodeError, StopIteration):
        pass
    return cleaned


def _limit_hit(sql: str, row_count: int) -> bool:
    match = _TRAILING_LIMIT.search(sql or "")
    return bool(match) and row_count >= int(match.group(1))


class NL2SQLService:
    def __init__(self, settings: AISettings | None = None):
        self.settings = settings or get_settings().ai

    async def ask(self, question: str, mode: str | None = None, summarize: bool | None = None) -> NL2SQLResult:
        requested_mode = resolve_mode(mode, self.settings)

        # 0. Guardrails de entrada: respuesta inmediata sin gastar el modelo
        decision = evaluate_input(question)
        if not decision.allowed:
            return self._blocked_result(question, requested_mode, decision.category,
                                        decision.message or messages.FAILED, "entrada")

        try:
            return await self._ask_with(get_provider(requested_mode, self.settings), question, summarize)
        except ProviderUnavailableError as exc:
            if not self.settings.allow_fallback:
                raise ServiceUnavailableError(str(exc), {"mode": requested_mode}) from exc
            logger.warning("Modo %s no disponible (%s); usando respaldo", requested_mode, exc)
            fallback = get_provider(other_mode(requested_mode), self.settings)
            try:
                result = await self._ask_with(fallback, question, summarize)
            except ProviderUnavailableError as fallback_exc:
                raise ServiceUnavailableError(
                    f"Ningún proveedor de IA disponible: {exc} / {fallback_exc}"
                ) from fallback_exc
            result.fallback_used = True
            result.warnings.append(f"El modo '{requested_mode}' no estaba disponible: {exc}")
            return result
        except ProviderError as exc:
            raise ServiceUnavailableError(f"El proveedor de IA falló: {exc}", {"mode": requested_mode}) from exc

    def _blocked_result(self, question: str, mode: str, category: str, message: str,
                        blocked_by: str) -> NL2SQLResult:
        try:
            described = get_provider(mode, self.settings).describe()
        except AppError:
            described = {"mode": mode, "provider": "-", "model": "-"}
        return NL2SQLResult(
            success=True, question=question, mode=mode, provider=described["provider"],
            model=described["model"], answer=message, explanation="", sql=None,
            category=category, blocked_by=blocked_by, timings={"totalMs": 0},
        )

    async def _ask_with(self, provider: LLMProvider, question: str, summarize: bool | None) -> NL2SQLResult:
        started = time.perf_counter()
        reference_date = await run_in_threadpool(_reference_date)
        system = prompts.build_system_prompt()
        prompt = prompts.build_question_prompt(question, reference_date)
        timings = {"llmMs": 0, "sqlMs": 0, "summaryMs": 0}
        attempts: list[dict[str, str]] = []
        base = dict(question=question, mode=provider.mode, provider=provider.name,
                    model=provider.model, reference_date=reference_date)

        def finish() -> dict[str, int]:
            timings["totalMs"] = int((time.perf_counter() - started) * 1000)
            return timings

        output: _LLMOutput | None = None
        result: QueryResult | None = None
        final_sql: str | None = None
        for _ in range(1 + max(0, self.settings.max_repair_attempts)):
            llm = await provider.generate(system, prompt, json_mode=True, schema=prompts.NL2SQL_SCHEMA)
            timings["llmMs"] += llm.latency_ms
            output = parse_llm_output(llm.text)

            # 2. El modelo clasificó la pregunta fuera del alcance permitido
            if output.category != messages.CATEGORY_HOSPITAL:
                return NL2SQLResult(
                    success=True, sql=None, category=output.category, blocked_by="modelo",
                    answer=messages.CATEGORY_MESSAGES.get(output.category, messages.OUT_OF_SCOPE),
                    explanation=output.explanation, timings=finish(), attempts=attempts, **base,
                )
            if not output.sql:
                return NL2SQLResult(
                    success=True, sql=None, answer=messages.NO_DATA, explanation=output.explanation,
                    timings=finish(), attempts=attempts, **base,
                )
            try:
                final_sql = validate_and_limit(output.sql, self.settings.max_rows)
                result = await run_in_threadpool(
                    execute_readonly, final_sql, self.settings.sql_timeout_seconds
                )
                timings["sqlMs"] += result.elapsed_ms
                break
            except (SQLGuardError, SQLExecutionError) as exc:
                attempts.append({"sql": output.sql, "error": str(exc)})
                prompt = prompts.build_repair_prompt(question, reference_date, output.sql, str(exc))

        if result is None or output is None:
            last = attempts[-1] if attempts else {"sql": None, "error": "sin respuesta"}
            return NL2SQLResult(
                success=False, sql=last["sql"], answer=messages.FAILED,
                explanation=output.explanation if output else "", timings=finish(),
                attempts=attempts, **base,
            )

        # 5. Defensa en profundidad: nada con apariencia de dato personal sale en los resultados
        rows, masked_columns = mask_personal_columns(result.columns, result.rows)
        warnings: list[str] = []
        if masked_columns:
            warnings.append(f"Se ocultaron datos personales en: {', '.join(masked_columns)}")
        labels = [humanize(col) for col in result.columns]
        limit_hit = _limit_hit(final_sql, result.row_count)

        # 6. Redacción de la respuesta
        answer = deterministic_answer(labels, rows, result.row_count, limit_hit)
        should_summarize = self.settings.summarize_results if summarize is None else summarize
        if should_summarize:
            try:
                # Salida JSON: la decodificación restringida impide que un modelo "thinking"
                # anteponga su razonamiento y reduce la latencia (ver ollama.py).
                summary = await provider.generate(
                    prompts.SUMMARY_SYSTEM_PROMPT,
                    prompts.build_summary_prompt(question, reference_date, labels, rows,
                                                 result.row_count, limit_hit),
                    json_mode=True, temperature=0.2, schema=prompts.SUMMARY_SCHEMA,
                )
                timings["summaryMs"] = summary.latency_ms
                answer = _parse_summary(summary.text) or answer
            except ProviderError as exc:
                warnings.append(f"No se pudo redactar la respuesta con IA: {exc}")

        # 7. Guardrails de salida
        answer, output_warnings = guard_answer(answer, labels, rows, result.row_count, question,
                                               reference_date, limit_hit)
        warnings.extend(output_warnings)

        return NL2SQLResult(
            success=True, sql=final_sql, answer=answer, explanation=output.explanation,
            columns=result.columns, column_labels=labels, rows=rows, row_count=result.row_count,
            truncated=result.row_count >= self.settings.max_rows,
            attempts=attempts, timings=finish(), warnings=warnings, **base,
        )
