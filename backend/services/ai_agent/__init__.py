"""
Agente de IA NL2SQL: pregunta en español -> SQL seguro -> respuesta en lenguaje natural.

- nl2sql_agent.py   Clase NL2SQLAgent: orquesta todo el flujo (patrón Facade).
- guardrails/       Filtros de entrada (sin LLM) y de salida (depuración de la respuesta).
- llm_providers/    Ollama, Gemini y APIs compatibles con OpenAI (patrón Strategy + Factory).
- prompts.py        Plantillas de prompt y esquemas JSON de salida.
- catalog.py        Tablas/columnas permitidas y descripción del esquema para el prompt.
- sql_guard.py      1.ª barrera: análisis estático del SQL con sqlglot.
- sql_executor.py   2.ª barrera: ejecución de solo lectura con authorizer de SQLite.
- column_labels.py  Etiquetas legibles en español para las columnas de resultados.
"""
