"""Etiquetas legibles en español para los resultados (no se exponen nombres de columnas)."""
from __future__ import annotations

import re

KNOWN_LABELS = {
    "oidingreso": "Ingreso", "idpaciente": "Paciente (ID)", "niveltriage": "Nivel de triage",
    "clasificaciontriage": "Clasificación de triage", "nombrediagnostico": "Diagnóstico",
    "codigodiagnostico": "Código CIE-10", "nombremedicamento": "Medicamento",
    "codigomedicamento": "Código", "stockactual": "Stock actual", "stockminimo": "Stock mínimo",
    "consumodiariopromedio": "Consumo diario promedio", "consumoultimos30dias": "Consumo últimos 30 días",
    "diasinventario": "Días de inventario", "fechaingreso": "Fecha de ingreso",
    "fechahospitalizacion": "Fecha de hospitalización", "fechavencimiento": "Vencimiento",
    "fechatriage": "Fecha de triage", "fechaatencion": "Fecha de atención", "fechacirugia": "Fecha de cirugía",
    "minutosespera": "Minutos de espera", "codigocama": "Cama", "nombrecama": "Cama",
    "subgrupocama": "Área", "grupocama": "Grupo de camas", "camasocupadas": "Camas ocupadas",
    "camastotales": "Camas totales", "porcentajeocupacion": "% de ocupación",
    "estadocirugia": "Estado de la cirugía", "numeroprocedimientos": "Procedimientos",
    "especialidadprincipal": "Especialidad principal", "diasestancia": "Días de estancia",
    "idmedico": "Médico (ID)", "turnoingreso": "Turno de ingreso", "viaingreso": "Vía de ingreso",
    "claseingreso": "Clase de ingreso", "nombreservicio": "Servicio o procedimiento",
    "areaservicio": "Área de servicio", "areaquirofano": "Quirófano", "ocupadadesde": "Ocupada desde",
}

_CAMEL = re.compile(r"(?<=[a-záéíóú])(?=[A-ZÁÉÍÓÚ])")


_ACCENTS = {
    "ocupacion": "ocupación", "dias": "días", "numero": "número", "medicos": "médicos",
    "medico": "médico", "cirugias": "cirugías", "cirugia": "cirugía", "atencion": "atención",
    "minimo": "mínimo", "maximo": "máximo", "categoria": "categoría", "diagnostico": "diagnóstico",
    "diagnosticos": "diagnósticos", "codigo": "código", "ultimos": "últimos", "ultimo": "último",
    "hospitalizacion": "hospitalización", "rotacion": "rotación", "clasificacion": "clasificación",
    "quirofano": "quirófano", "pediatria": "pediatría", "admision": "admisión", "via": "vía",
}


def humanize(column: str) -> str:
    key = column.lower().replace("_", "")
    if key in KNOWN_LABELS:
        return KNOWN_LABELS[key]
    words = _CAMEL.sub(" ", column).replace("_", " ").strip().lower()
    words = re.sub(r"\bpct\b", "%", words)
    words = re.sub(r"\bmin\b", "(min)", words)
    words = " ".join(_ACCENTS.get(w, w) for w in words.split())
    return words[:1].upper() + words[1:] if words else column
