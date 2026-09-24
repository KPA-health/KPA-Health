"""
Motor NL2SQL con un proveedor LLM falso (no requiere Ollama ni Gemini):
switch de modo, autocorrección, privacidad y ejecución real contra SQLite.
"""
import json

import pytest

from backend.services.ai_agent.llm_providers.base import LLMProvider, LLMResult, ProviderHealth, ProviderUnavailableError
from backend.services.ai_agent.prompts import SUMMARY_SYSTEM_PROMPT


class FakeProvider(LLMProvider):
    name = "fake"
    model = "fake-model"

    def __init__(self, mode: str, answers: list[dict] | None = None, unavailable: bool = False):
        self.mode = mode
        self._answers = list(answers or [])
        self._unavailable = unavailable
        self.prompts: list[str] = []

    async def generate(self, system, prompt, *, json_mode=True, temperature=0.0, schema=None):
        if self._unavailable:
            raise ProviderUnavailableError("sin conexión")
        self.prompts.append(prompt)
        return LLMResult(json.dumps(self._answers.pop(0)), self.name, self.model, 1)

    async def health(self):
        return ProviderHealth(not self._unavailable, "fake")


@pytest.fixture
def use_providers(monkeypatch):
    """Sustituye la fábrica de proveedores por proveedores falsos por modo."""
    def install(**by_mode):
        monkeypatch.setattr("backend.services.ai_agent.nl2sql_agent.get_provider",
                            lambda mode, settings=None: by_mode[mode])
        return by_mode
    return install


UCI_SQL = "SELECT COUNT(*) AS camas FROM EstadoCamas WHERE Servicio = 'Cuidados Intensivos (UCI)'"


def test_local_mode_returns_data_and_exact_sql(client, use_providers):
    use_providers(local=FakeProvider("local", [{"sql": UCI_SQL, "explanation": "Cuenta camas UCI"}]))
    body = client.post("/api/ai/query", json={"question": "camas UCI", "mode": "local"}).json()
    assert body["success"] is True and body["mode"] == "local"
    assert body["sql"].startswith(UCI_SQL) and body["columns"] == ["camas"]
    assert body["rowCount"] == 1 and isinstance(body["rows"][0][0], int)


def test_cloud_mode_is_selected_by_request(client, use_providers):
    providers = use_providers(
        local=FakeProvider("local", unavailable=True),
        cloud=FakeProvider("cloud", [{"sql": UCI_SQL, "explanation": "x"}]),
    )
    body = client.post("/api/ai/query", json={"question": "camas UCI", "mode": "cloud"}).json()
    assert body["mode"] == "cloud" and body["success"] is True
    assert len(providers["cloud"].prompts) == 1


def test_self_repair_after_policy_violation(client, use_providers):
    provider = FakeProvider("local", [
        {"sql": "SELECT NombrePaciente FROM Paciente", "explanation": "x"},
        {"sql": "SELECT COUNT(*) AS pacientes FROM Paciente", "explanation": "x"},
    ])
    use_providers(local=provider)
    body = client.post("/api/ai/query", json={"question": "cuántos pacientes", "mode": "local"}).json()
    assert body["success"] is True and len(body["attempts"]) == 1
    assert "datos personales" in body["attempts"][0]["error"]
    assert "Tu consulta anterior falló" in provider.prompts[1]


def test_personal_data_blocked_before_calling_the_model(client, use_providers):
    provider = FakeProvider("local", [])
    use_providers(local=provider)
    body = client.post("/api/ai/query", json={"question": "nombres de pacientes", "mode": "local"}).json()
    assert body["success"] is True and body["sql"] is None
    assert body["category"] == "personal_data" and body["blockedBy"] == "input_guard"
    assert provider.prompts == []  # el guardrail respondió sin gastar el modelo


def test_model_classifies_out_of_scope(client, use_providers):
    use_providers(local=FakeProvider("local", [
        {"category": "out_of_scope", "sql": None, "explanation": "No es del hospital"}
    ]))
    body = client.post("/api/ai/query", json={"question": "¿Quién ganó ayer?", "mode": "local"}).json()
    assert body["category"] == "out_of_scope" and body["blockedBy"] == "model"
    assert body["answer"].startswith("Solo puedo responder sobre la operación")


def test_english_question_is_rejected_in_spanish(client, use_providers):
    provider = FakeProvider("local", [])
    use_providers(local=provider)
    body = client.post("/api/ai/query", json={"question": "How many ICU beds are occupied today?"}).json()
    assert body["category"] == "unsupported_language" and "español" in body["answer"]
    assert provider.prompts == []


def test_hospital_question_without_data_uses_canned_message(client, use_providers):
    use_providers(local=FakeProvider("local", [{"category": "hospital", "sql": None, "explanation": "x"}]))
    body = client.post("/api/ai/query", json={"question": "¿Cuántas ambulancias hay?", "mode": "local"}).json()
    assert body["sql"] is None and body["answer"].startswith("No cuento con información")


def test_summary_is_sanitized_and_labels_are_human(client, use_providers):
    provider = FakeProvider("local", [{"sql": UCI_SQL, "explanation": "x"}])

    async def summary(system, prompt, *, json_mode=True, temperature=0.0, schema=None):
        if system != SUMMARY_SYSTEM_PROMPT:
            return await FakeProvider.generate(provider, system, prompt)
        return LLMResult('{"answer": "La consulta SQL devolvió 1 fila en la base de datos: 25 camas."}', "fake", "m", 1)

    provider.generate = summary
    use_providers(local=provider)
    body = client.post("/api/ai/query", json={"question": "camas UCI", "mode": "local", "summarize": True}).json()
    lowered = body["answer"].lower()
    for term in ("sql", "fila", "base de datos", "consulta"):
        assert term not in lowered, body["answer"]
    assert body["columnLabels"] == ["Camas"]


def test_personal_looking_columns_are_masked(client, use_providers):
    sql = "SELECT CodigoCama AS nombre_paciente, Servicio FROM EstadoCamas LIMIT 3"
    use_providers(local=FakeProvider("local", [{"sql": sql, "explanation": "x"}]))
    body = client.post("/api/ai/query", json={"question": "camas por servicio", "mode": "local"}).json()
    assert all(row[0] == "•••" for row in body["rows"]) and body["warnings"]


def test_unavailable_provider_returns_503_without_fallback(client, use_providers):
    use_providers(local=FakeProvider("local", unavailable=True))
    response = client.post("/api/ai/query", json={"question": "camas UCI", "mode": "local"})
    assert response.status_code == 503 and "message" in response.json()


def test_invalid_mode_is_rejected(client):
    assert client.post("/api/ai/query", json={"question": "hola", "mode": "marte"}).status_code == 422


def test_voice_disabled_returns_501(client):
    response = client.post("/api/ai/transcribe", files={"audio": ("a.webm", b"123", "audio/webm")})
    assert response.status_code == 501 and "message" in response.json()
