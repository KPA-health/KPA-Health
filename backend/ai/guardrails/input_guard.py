"""
Guardrails de ENTRADA (patrón Chain of Responsibility).

Cada eslabón revisa la pregunta y decide: bloquearla con una respuesta fija
en español, o dejarla pasar al siguiente. Si todos la dejan pasar, la
pregunta llega al modelo (que tiene su propia regla de alcance en el prompt).

Ventajas: respuestas inmediatas (sin gastar GPU ni tokens) para lo que es
evidente, y comportamiento determinista y auditable.
"""
from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.ai.guardrails import messages
from backend.ai.guardrails.language import detect_language


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    category: str
    message: str | None = None
    guard: str | None = None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", text).strip()


# Raíces de vocabulario hospitalario (sin tildes, en minúsculas)
HOSPITAL_TERMS = re.compile(
    r"\b(hospital\w*|camas?|uci\w*|pacientes?|ingres\w*|egres\w*|altas?|triag\w*|triaj\w*|urgenc\w*|"
    r"emergenc\w*|esper\w*|atencion\w*|atendid\w*|medicament\w*|farmac\w*|insumos?|stock|inventari\w*|"
    r"cirug\w*|quirof\w*|quirurg\w*|servicios?|especialid\w*|medic\w*|doctor\w*|enfermer\w*|diagnost\w*|"
    r"ocupa\w*|hospitaliz\w*|pediatr\w*|neonat\w*|gineco\w*|obstetr\w*|partos?|cesare\w*|consultas?|"
    r"turnos?|capacidad|disponib\w*|traslad\w*|recuperacion|intermedi\w*|intensiv\w*|laboratori\w*|"
    r"procedimient\w*|demanda|rotacion|consum\w*|vencimient\w*|cie|enfermedad\w*|neumoni\w*|infecci\w*|"
    r"dengue|covid\w*|fractur\w*|asma|kpi|indicador\w*|estancia\w*|morbilidad|mortalidad|epidemiolog\w*|"
    r"admision\w*|censo|reingres\w*|programad\w*|cirujan\w*|antibiotic\w*|oxigeno|sala\w*|box|"
    r"eps|asegurador\w*|regimen|municipio\w*|triage|signos vitales|fiebre|sintomas?|salud)\b"
)

# Temas claramente ajenos a la operación del hospital
OFF_TOPIC_TERMS = re.compile(
    r"\b(clima|lluvi\w*|llover|pronostico del tiempo|temperatura ambiente|soleado|gobierno\w*|"
    r"president\w*|eleccion\w*|votacion\w*|politic\w*|congres\w*|senado\w*|alcald\w*|gobernador\w*|"
    r"ministr\w*|partido politico|futbol\w*|deport\w*|mundial|liga|goles?|pelicula\w*|series? de tv|"
    r"musica|cancion\w*|recetas? de cocina|cocinar|chistes?|horoscopo|bitcoin|criptomoned\w*|dolar\w*|"
    r"bolsa de valores|noticias?|guerra\w*|religion\w*|capital de|poema\w*|cuento\w*|python|javascript|"
    r"programar|codigo fuente|traduc\w*|videojueg\w*|turismo|restaurante\w*|celebridad\w*|farandula|"
    r"loteria|apuestas?|chiste)\b"
)

GREETING = re.compile(
    r"^(hola|holi|hey|buen(os|as)\s+(dias|tardes|noches)|buenas|saludos|que tal|como estas|"
    r"quien eres|que eres|que puedes hacer|que sabes hacer|ayuda|como funcionas|en que me puedes ayudar)"
    r"[\s!¡?¿.,]*$"
)
THANKS = re.compile(r"^(muchas\s+)?gracias[\s!¡.,]*(por todo|muy amable)?[\s!¡.,]*$")

_PERSON = r"(pacientes?|personas?|usuarios?|ingresad\w*|hospitalizad\w*|medic(o|a|os|as)|doctor\w*|enfermer\w*|familiar\w*)"
PERSONAL_DATA = [
    re.compile(rf"\b(nombres?|apellidos?)\b.*\b{_PERSON}\b"),
    re.compile(rf"\b{_PERSON}\b.*\b(nombres?|apellidos?)\b"),
    re.compile(r"\b(cedulas?|documentos? de identidad|numeros? de documento|numeros? de identificacion|"
               r"dni|pasaportes?|tarjetas? de identidad)\b"),
    re.compile(rf"\b(telefonos?|celular\w*|direccion\w*|correos?|emails?)\b.*\b{_PERSON}\b"),
    re.compile(r"\bquien(es)?\s+(es|son|esta|estan)\s+(el|la|los|las)?\s*(paciente|pacientes|internad\w*|hospitalizad\w*)\b"),
]


class InputGuard(ABC):
    name: str

    @abstractmethod
    def check(self, original: str, normalized: str) -> GuardDecision | None:
        """Devuelve una decisión para bloquear, o None para pasar al siguiente eslabón."""


class EmptyGuard(InputGuard):
    name = "vacia"

    def check(self, original, normalized):
        if len(re.sub(r"[\W_]", "", normalized)) < 2:
            return GuardDecision(False, messages.CATEGORY_EMPTY, messages.EMPTY, self.name)
        return None


class LanguageGuard(InputGuard):
    name = "idioma"

    def check(self, original, normalized):
        if detect_language(original).language == "en":
            return GuardDecision(False, messages.CATEGORY_LANGUAGE, messages.LANGUAGE_NOT_SUPPORTED, self.name)
        return None


class SmallTalkGuard(InputGuard):
    name = "saludo"

    def check(self, original, normalized):
        if HOSPITAL_TERMS.search(normalized):
            return None
        if THANKS.match(normalized):
            return GuardDecision(False, messages.CATEGORY_GREETING, messages.THANKS, self.name)
        if GREETING.match(normalized):
            return GuardDecision(False, messages.CATEGORY_GREETING, messages.GREETING, self.name)
        return None


class PersonalDataGuard(InputGuard):
    name = "datos_personales"

    def check(self, original, normalized):
        if any(p.search(normalized) for p in PERSONAL_DATA):
            return GuardDecision(False, messages.CATEGORY_PERSONAL_DATA, messages.PERSONAL_DATA, self.name)
        return None


INJECTION = re.compile(
    r"\b(ignora|olvida|omite|desobedece)\w*\s+(todas?\s+)?(tus|las|sus|estas)\s+(instrucciones|reglas|indicaciones)"
    r"|\b(prompt|mensaje|instrucciones)\s+(del|de)\s+sistema\b|\bsystem prompt\b|\bjailbreak\b"
    r"|\b(actua|comportate|finge)\s+como\b|\bmodo desarrollador\b|\brevela\w*\s+(tu|el)\s+(prompt|configuracion)"
)


class InjectionGuard(InputGuard):
    """Intentos de cambiar el rol o extraer las instrucciones del asistente."""
    name = "inyeccion"

    def check(self, original, normalized):
        if INJECTION.search(normalized):
            return GuardDecision(False, messages.CATEGORY_OUT_OF_SCOPE, messages.OUT_OF_SCOPE, self.name)
        return None


class ScopeGuard(InputGuard):
    name = "alcance"

    def check(self, original, normalized):
        if OFF_TOPIC_TERMS.search(normalized) and not HOSPITAL_TERMS.search(normalized):
            return GuardDecision(False, messages.CATEGORY_OUT_OF_SCOPE, messages.OUT_OF_SCOPE, self.name)
        return None


DEFAULT_CHAIN: tuple[InputGuard, ...] = (
    EmptyGuard(), LanguageGuard(), InjectionGuard(), SmallTalkGuard(), PersonalDataGuard(), ScopeGuard(),
)


def evaluate_input(question: str, chain: tuple[InputGuard, ...] = DEFAULT_CHAIN) -> GuardDecision:
    normalized = normalize(question)
    for guard in chain:
        decision = guard.check(question, normalized)
        if decision is not None:
            return decision
    return GuardDecision(True, messages.CATEGORY_HOSPITAL)
