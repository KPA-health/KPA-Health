"""
Guardrails del asistente KPA-Health (parte del agente NL2SQL).

Entrada (Chain of Responsibility, sin LLM): vacío → idioma → inyección →
saludo → datos personales → alcance hospitalario. Salida: depuración de términos técnicos,
datos personales y verificación de idioma español.

- input_guard.py   Cadena de filtros de entrada.
- output_guard.py  Depuración y verificación de la respuesta (anti-alucinación de cifras).
- language.py      Detección ligera español/inglés.
- messages.py      Respuestas canónicas y categorías.
"""
