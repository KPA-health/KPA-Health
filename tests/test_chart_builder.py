"""
Gráficos del chat: tipo y datos se deciden con código sobre las filas reales (0 tokens del LLM).
"""
import json

from backend.services.ai_agent import prompts
from backend.services.ai_agent.chart_builder import LABEL_KEY, build_chart
from backend.services.ai_agent.llm_providers.base import LLMProvider, LLMResult, ProviderHealth


def test_prompt_does_not_spend_tokens_on_charts():
    assert "tipo_grafico" not in prompts.build_system_prompt()
    assert "tipo_grafico" not in prompts.NL2SQL_SCHEMA["properties"]


def test_categories_with_one_measure_become_bar_points():
    chart_type, data = build_chart(["Servicio", "ingresos"], ["Servicio", "Ingresos"], [["UCI", 12], ["Urgencias", 40]])
    assert chart_type == "bar"
    assert data == [{LABEL_KEY: "UCI", "Ingresos": 12}, {LABEL_KEY: "Urgencias", "Ingresos": 40}]


def test_single_value_identifier_lists_and_empty_results_have_no_chart():
    assert build_chart(["camas"], ["Camas"], [[25]]) == (None, [])
    assert build_chart(["OidIngreso", "Servicio"], ["Ingreso", "Servicio"], [[1, "UCI"], [2, "UCI"]]) == (None, [])
    assert build_chart(["Servicio", "n"], ["Servicio", "N"], []) == (None, [])


def test_single_row_percentage_becomes_a_gauge():
    chart_type, data = build_chart(
        ["camas_ocupadas", "camas_totales", "porcentaje_ocupacion"],
        ["Camas ocupadas", "Camas totales", "Porcentaje ocupación"], [[25, 37, 67.6]],
    )
    assert chart_type == "gauge"
    assert data == [{LABEL_KEY: "Porcentaje ocupación", "Valor": 67.6}]


def test_single_row_without_percentage_compares_counts():
    chart_type, data = build_chart(
        ["cirugias_realizadas", "cirugias_no_realizadas"], ["Realizadas", "No realizadas"], [[80, 20]],
    )
    assert chart_type == "bar"
    assert [p[LABEL_KEY] for p in data] == ["Realizadas", "No realizadas"]
    assert build_chart(["a", "b"], ["A", "B"], [[80, 20]], "distribución de cirugías")[0] == "pie"


def test_distribution_question_or_share_column_becomes_pie():
    rows = [["Subsidiado", 293], ["Contributivo", 120], ["Especial", 12]]
    assert build_chart(["Regimen", "n"], ["Régimen", "Pacientes"], rows)[0] == "bar"
    assert build_chart(["Regimen", "n"], ["Régimen", "Pacientes"], rows, "Distribución por régimen")[0] == "pie"
    share = [["Masculino", 191, 53.4], ["Femenino", 167, 46.6]]
    assert build_chart(["Sexo", "ingresos", "porcentaje"], ["Sexo", "Ingresos", "%"], share)[0] == "pie"


def test_percentages_that_do_not_add_up_to_100_stay_as_bars():
    rows = [["UCI", 30, 81.0], ["Urgencias", 20, 95.0], ["Pediatría", 10, 60.0]]
    assert build_chart(["Servicio", "ocupadas", "porcentaje_ocupacion"], ["Servicio", "Ocupadas", "%"], rows)[0] == "bar"


def test_pie_with_too_many_slices_falls_back_to_bar():
    rows = [[f"S{i}", i + 1] for i in range(12)]
    assert build_chart(["Servicio", "n"], ["Servicio", "N"], rows, "distribución por servicio")[0] == "bar"


def test_dates_become_a_line():
    chart_type, _ = build_chart(["mes", "ingresos"], ["Mes", "Ingresos"], [["2025-01", 3], ["2025-02", 5]])
    assert chart_type == "line"


def test_month_by_service_is_pivoted_into_one_series_per_service():
    rows = [["2025-01", "UCI", 70.0], ["2025-01", "Urgencias", 50.0], ["2025-02", "UCI", 75.0]]
    chart_type, data = build_chart(["mes", "Servicio", "ocupacion_pct"], ["Mes", "Servicio", "Ocupación %"], rows)
    assert chart_type == "line"
    assert data == [
        {LABEL_KEY: "2025-01", "UCI": 70.0, "Urgencias": 50.0},
        {LABEL_KEY: "2025-02", "UCI": 75.0, "Urgencias": None},
    ]


def test_integer_first_column_without_text_is_the_category():
    chart_type, data = build_chart(
        ["NivelTriage", "pacientes", "porcentaje"], ["Nivel Triage", "Pacientes", "Porcentaje"],
        [[1, 22, 7.0], [2, 80, 25.5], [3, 150, 47.8], [4, 62, 19.7]],
    )
    assert chart_type == "pie"
    assert data[0] == {LABEL_KEY: "Nivel Triage 1", "Pacientes": 22}


class ChartProvider(LLMProvider):
    name = "fake"
    model = "fake-model"
    mode = "local"

    async def generate(self, system, prompt, *, json_mode=True, temperature=0.0, schema=None):
        if "Primeros resultados" in prompt:
            return LLMResult(json.dumps({"mensaje_texto": "Urgencias concentra la mayoría de las camas."}), self.name, self.model, 1)
        sql = "SELECT Servicio, COUNT(*) AS camas FROM EstadoCamas GROUP BY Servicio ORDER BY camas DESC"
        return LLMResult(json.dumps({"category": "hospital", "sql": sql, "explanation": "x", "tipo_grafico": "pie"}),
                         self.name, self.model, 1)

    async def health(self):
        return ProviderHealth(True, "fake")


def test_api_returns_text_chart_data_and_type(client, monkeypatch):
    monkeypatch.setattr("backend.services.ai_agent.nl2sql_agent.get_provider", lambda mode, settings=None: ChartProvider())
    body = client.post("/api/ai/query", json={"question": "camas por servicio", "mode": "local", "summarize": True}).json()
    assert body["mensaje_texto"] == body["answer"]
    assert body["tipo_grafico"] == "bar"   # lo decide el código, no lo que diga el modelo
    assert len(body["datos_grafico"]) == body["rowCount"] > 1
    assert set(body["datos_grafico"][0]) == {LABEL_KEY, body["columnLabels"][1]}

