"""Pruebas unitarias de la primera barrera de seguridad del agente (sin base de datos)."""
import pytest

from backend.services.ai_agent.nl2sql_agent import parse_llm_output
from backend.services.ai_agent.sql_guard import SQLGuardError, validate_and_limit


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM EstadoCamas WHERE Estado = 'Ocupada'",
    "WITH x AS (SELECT Servicio, COUNT(*) n FROM VistaIngresos GROUP BY 1) SELECT * FROM x",
    "SELECT Servicio FROM VistaIngresos UNION SELECT Servicio FROM EstadoCamas",
    "SELECT Sexo, COUNT(*) FROM Paciente GROUP BY Sexo",
])
def test_allows_read_only_queries(sql):
    assert "LIMIT" in validate_and_limit(sql, 100).upper()


@pytest.mark.parametrize("sql, reason", [
    ("DELETE FROM Ingresos", "lectura"),
    ("DROP TABLE Paciente", "lectura"),
    ("SELECT 1; DROP TABLE Ingresos", "una sentencia"),
    ("PRAGMA table_info(Paciente)", "lectura"),
    ("SELECT name FROM sqlite_master", "no permitidas"),
    ("SELECT * FROM IngresoGestion", "no permitidas"),
    ("SELECT NombrePaciente FROM Paciente", "datos personales"),
    ("SELECT p.FechaNacimiento AS f FROM Paciente p", "datos personales"),
    ("SELECT MotivoConsulta FROM Triage", "datos personales"),
    ("SELECT * FROM Paciente", "SELECT *"),
])
def test_blocks_unsafe_queries(sql, reason):
    with pytest.raises(SQLGuardError, match=reason):
        validate_and_limit(sql, 100)


def test_limit_is_injected_or_capped():
    assert validate_and_limit("SELECT Servicio FROM EstadoCamas", 50).endswith("LIMIT 50")
    assert "LIMIT 10" in validate_and_limit("SELECT Servicio FROM EstadoCamas LIMIT 10", 50)
    assert "LIMIT 50" in validate_and_limit("SELECT Servicio FROM EstadoCamas LIMIT 5000", 50)


def test_parse_llm_output_variants():
    assert parse_llm_output('{"sql": "SELECT 1;", "explanation": "x"}').sql == "SELECT 1"
    assert parse_llm_output('{"sql": null, "explanation": "no"}').sql is None
    assert parse_llm_output("<think>...</think>```sql\nSELECT 2\n```").sql == "SELECT 2"
    assert parse_llm_output("Claro: SELECT 3 FROM EstadoCamas").sql == "SELECT 3 FROM EstadoCamas"
