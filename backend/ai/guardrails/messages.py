"""
Mensajes fijos del asistente (siempre en español).

Se usan respuestas canónicas en lugar de texto libre del LLM para los casos
de rechazo: son consistentes, no inventan nada y no responden con preguntas.
"""

INSTITUTION = "Hospital Susana López de Valencia E.S.E."

WELCOME = f"¡Hola! Soy tu asistente KPA-Health del {INSTITUTION} ¿En qué puedo ayudarte hoy?"

CAPABILITIES = (
    "Puedo ayudarte con la ocupación de camas por servicio, los tiempos de espera en urgencias "
    "por nivel de triage, los pacientes hospitalizados, las cirugías programadas y realizadas, "
    "y el inventario y consumo de medicamentos."
)

GREETING = f"¡Hola! Soy tu asistente KPA-Health del {INSTITUTION} {CAPABILITIES}"

THANKS = "Con gusto. Aquí estaré para ayudarte con cualquier otro dato sobre la operación del hospital."

EMPTY = "Escribe una pregunta sobre la operación del hospital para poder ayudarte."

OUT_OF_SCOPE = f"Solo puedo responder sobre la operación del {INSTITUTION} {CAPABILITIES}"

LANGUAGE_NOT_SUPPORTED = (
    "Solo puedo atender preguntas escritas en español. Por favor, escribe tu pregunta en español."
)

PERSONAL_DATA = (
    "Por protección de datos personales no puedo entregar nombres, apellidos, documentos de identidad "
    "ni datos de contacto. Puedo darte cifras agregadas o identificar los casos por su número de ingreso."
)

NO_DATA = (
    "No cuento con información suficiente para responder esa pregunta con los datos disponibles "
    "del hospital."
)

NO_RESULTS = "No encontré resultados para esa pregunta en la información disponible del hospital."

FAILED = (
    "No pude obtener esa información en este momento. Intenta formular la pregunta con otras palabras."
)

# Categorías que puede devolver la cadena de guardrails o el modelo
CATEGORY_HOSPITAL = "hospital"
CATEGORY_GREETING = "saludo"
CATEGORY_OUT_OF_SCOPE = "fuera_de_alcance"
CATEGORY_LANGUAGE = "idioma_no_soportado"
CATEGORY_PERSONAL_DATA = "datos_personales"
CATEGORY_EMPTY = "vacia"

CATEGORY_MESSAGES = {
    CATEGORY_OUT_OF_SCOPE: OUT_OF_SCOPE,
    CATEGORY_LANGUAGE: LANGUAGE_NOT_SUPPORTED,
    CATEGORY_PERSONAL_DATA: PERSONAL_DATA,
    CATEGORY_EMPTY: EMPTY,
}
