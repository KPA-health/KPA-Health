from typing import Dict, Any, Tuple
import yaml
import json
from backend.query.catalog import generate_template_sql, catalog
from backend.models.ollama import OllamaClient
from backend.models.openai_compatible import OpenAICompatibleClient
from backend.models.base import ModelResult

def load_profiles() -> Dict[str, Any]:
    with open("config/models.yaml", "r") as f:
        return yaml.safe_load(f)

async def route_query(question: str, profile_name: str, filters: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], str, str, str, str]:
    # Returns (status, message, result_filters, metric_id, sql, params, source, unit)
    
    # 1. Very basic intent matching (Hybrid template matching)
    q_lower = question.lower()
    matched_metric = None
    if "cuántos ingresos" in q_lower or "total de ingresos" in q_lower:
        matched_metric = "admissions_count"
    elif "tiempo promedio de espera" in q_lower or "espera promedio" in q_lower:
        matched_metric = "wait_mean"
    elif "distribución de triage" in q_lower or "clasificación de triage" in q_lower:
        matched_metric = "triage_distribution"
    elif "medicamentos dispensados" in q_lower:
        matched_metric = "medication_dispensed"
    elif "servicios por especialidad" in q_lower:
        matched_metric = "services_by_specialty"
        
    if matched_metric:
        sql, params = generate_template_sql(matched_metric, filters)
        metric_info = catalog.get_metric(matched_metric)
        return "ok", "Respuesta mediante plantilla", filters, matched_metric, sql, params, "template", metric_info.get("unit")
        
    # 2. Local NL2SQL Fallback
    profiles = load_profiles()
    profile = profiles.get("profiles", {}).get(profile_name)
    if not profile or not profile.get("enabled", False):
        return "unavailable", "Model profile is disabled or not found.", filters, None, None, None, "none", None
        
    provider = profile.get("provider")
    if provider == "ollama":
        client = OllamaClient()
    elif provider == "openai_compatible":
        client = OpenAICompatibleClient()
    else:
        return "unavailable", "Provider not implemented yet.", filters, None, None, None, "none", None
        
    # Construct prompt with schema context
    schema_context = "\n".join([f"- {m['metric_id']}: {m['definition']}" for m in catalog.list_metrics()])
    prompt = f"""
    Eres un asistente de NL2SQL híbrido para un hospital. 
    Responde en JSON con las claves: status (ok|clarify|insufficient_data|reject), sql, params (diccionario), metric_id, filters, unit, message.
    Usa solo las siguientes métricas y vistas permitidas.
    
    Catálogo:
    {schema_context}
    
    Pregunta: {question}
    Filtros solicitados: {json.dumps(filters)}
    """
    
    result: ModelResult = await client.generate(prompt, profile)
    
    if result.status == "ok":
        return result.status, result.message, result.filters, result.metric_id, result.sql, result.params, "local", result.unit
    else:
        return result.status, result.message, filters, None, None, None, "local", None
