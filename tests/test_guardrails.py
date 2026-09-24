"""Guardrails del asistente: idioma, alcance, saludos, datos personales y depuración de salida."""
import pytest

from backend.ai.guardrails.input_guard import evaluate_input
from backend.ai.guardrails.language import detect_language
from backend.ai.guardrails.output_guard import contains_forbidden_terms, guard_answer, sanitize_text
from backend.core.privacy import is_personal_column, scrub_text


@pytest.mark.parametrize("question, category", [
    ("¿Cuántas camas de UCI están ocupadas hoy?", "hospital"),
    ("Top 10 medicamentos de mayor rotación", "hospital"),
    ("¿Cómo afecta el clima a los ingresos por neumonía?", "hospital"),
    ("Nombres de los medicamentos con stock crítico", "hospital"),
    ("How many ICU beds are occupied today?", "idioma_no_soportado"),
    ("What is the average wait time in urgencias?", "idioma_no_soportado"),
    ("¿Cómo estará el clima mañana en Popayán?", "fuera_de_alcance"),
    ("¿Qué opinas del gobierno?", "fuera_de_alcance"),
    ("¿Quién ganó el partido de fútbol ayer?", "fuera_de_alcance"),
    ("¿Cuál es la capital de Francia?", "fuera_de_alcance"),
    ("hola", "saludo"),
    ("Buenos días!", "saludo"),
    ("gracias", "saludo"),
    ("¿Cuál es la cédula del paciente 614996?", "datos_personales"),
    ("Dame los nombres de los pacientes en UCI", "datos_personales"),
    ("dame el nombre del médico de guardia", "datos_personales"),
    ("??", "vacia"),
])
def test_input_guard_categories(question, category):
    assert evaluate_input(question).category == category


def test_language_detection():
    assert detect_language("¿Cuál es el promedio de espera?").language == "es"
    assert detect_language("Show me the patients in the ICU").language == "en"
    assert detect_language("UCI").language == "unknown"


@pytest.mark.parametrize("raw", [
    "La consulta devolvió 5 filas de pacientes en la base de datos.",
    "Según la consulta SQL hay 25 camas ocupadas.",
    "La tabla muestra 3 registros por columna.",
])
def test_output_sanitizer_removes_technical_terms(raw):
    assert not contains_forbidden_terms(sanitize_text(raw))


def test_clinical_uses_of_consulta_are_kept():
    text = "El motivo de consulta más común fue fiebre y hubo 30 consultas externas."
    assert sanitize_text(text) == text and not contains_forbidden_terms(text)


def test_english_answer_falls_back_to_deterministic_spanish():
    answer, warnings = guard_answer("There are 25 occupied beds", ["Camas ocupadas", "Camas totales"], [[25, 37]])
    assert answer == "Camas ocupadas: 25; Camas totales: 37." and warnings


def test_privacy_helpers():
    assert scrub_text("El paciente con CC 1061234567 está en UCI.") == "El paciente con CC ••• está en UCI."
    assert scrub_text("Hay 1234567 ingresos") == "Hay 1234567 ingresos"
    assert is_personal_column("nombre_paciente") and is_personal_column("Documento")
    assert not is_personal_column("NombreMedicamento") and not is_personal_column("NombreDiagnostico")


def test_numeric_grounding_rejects_invented_counts():
    rows = [["A02BO", "OMEPRAZOL 40 mg", 97.0], ["A10BK", "DAPAGLIFLOZINA 10 mg", 21.0]]
    labels = ["Código", "Medicamento", "Stock actual"]
    answer, warnings = guard_answer("Hay 15 medicamentos con stock crítico.", labels, rows, 50, "stock crítico", None, True)
    assert answer.startswith("Encontré al menos 50 resultados") and "OMEPRAZOL" in answer
    ok, _ = guard_answer("Hay al menos 50 medicamentos, como OMEPRAZOL 40 mg con 97 unidades.", labels, rows, 50, "q", None, True)
    assert ok.startswith("Hay al menos 50")


def test_reasoning_leak_falls_back():
    leak = "Okay, let's tackle this. The user is asking how many beds. Hay 25 camas ocupadas."
    answer, _ = guard_answer(leak, ["Camas ocupadas"], [[25]], 1, "camas")
    assert answer == "Camas ocupadas: 25."
