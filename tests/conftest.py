"""
Fixtures de prueba.

Se construye una base de datos TEMPORAL con el mismo ETL de setup_db.py
(una muestra de los archivos de data/), así las pruebas de escritura nunca
tocan hospital.db.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import setup_db

SAMPLE_ROWS = {"Servicios": 30_000, "MedicamentoInsumo": 30_000}


def _build_sample_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    setup_db.create_schema(conn)
    for table in setup_db.LOAD_ORDER:
        source = Path(setup_db.DATA_DIR) / f"{table}.txt"
        nrows = SAMPLE_ROWS.get(table)
        df = pd.read_csv(source, sep="|", encoding="utf-8", low_memory=False, nrows=nrows)
        setup_db.clean_dataframe(df, table).to_sql(table, conn, if_exists="append", index=False)
    conn.close()


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("db") / "hospital_test.db"
    _build_sample_db(path)
    return path


@pytest.fixture(scope="session")
def client(db_path):
    os.environ.update({
        "DATABASE_PATH": str(db_path),
        "AI_SUMMARIZE_RESULTS": "false",
        "AI_ALLOW_FALLBACK": "false",
        "GEMINI_API_KEY": "",
        "VOICE_ENABLED": "false",
        "AUTH_ENABLED": "false",           # las pruebas de contrato no dependen del login
        "JWT_SECRET": "secreto-de-pruebas-no-usar-en-produccion",
        "WHISPER_PRELOAD": "false",
    })
    from backend.core.config import get_settings
    from backend.ai.speech.base import get_speech_provider
    get_settings.cache_clear()
    get_speech_provider.cache_clear()

    from fastapi.testclient import TestClient
    from backend.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
