"""
Guardrails del asistente KPA-Health.

Entrada (Chain of Responsibility, sin LLM): vacío → idioma → inyección →
saludo → datos personales → alcance hospitalario. Salida: depuración de términos técnicos,
datos personales y verificación de idioma español.
"""
