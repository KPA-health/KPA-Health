"""DTOs de /patients (ver frontend/js/services/patientService.js y mockData.js)."""
from __future__ import annotations

import re

from pydantic import ConfigDict, Field, field_validator, ValidationInfo

from backend.schemas.common import CamelModel


class Vitals(CamelModel):
    bp: str | None = None
    hr: str | None = None
    temp: str | None = None
    spo2: str | None = None


class InputVitals(Vitals):
    bp: str | None = Field(default=None, max_length=32, pattern=r"^[^<>\x00-\x1f]*$")
    hr: str | None = Field(default=None, max_length=32, pattern=r"^[^<>\x00-\x1f]*$")
    temp: str | None = Field(default=None, max_length=32, pattern=r"^[^<>\x00-\x1f]*$")
    spo2: str | None = Field(default=None, max_length=32, pattern=r"^[^<>\x00-\x1f]*$")


_TEXT_LIMITS = {
    "name": 120, "dni": 32, "phone": 32, "allergies": 500,
    "symptoms": 2000, "diagnosis": 2000, "notes": 2000,
    "discharge_notes": 2000, "department": 120, "room_number": 80,
    "bed_id": 80, "doctor_assigned_id": 80, "doctor_assigned_name": 120,
    "doctor_name": 120, "status": 80, "gender": 40,
    "blood_type": 32, "discharge_date": 40,
}
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ ._/'-]+$")
_SQL_COMMAND = re.compile(r"(?i)(?:;\s*(?:select|insert|update|delete|drop|alter|union)\b|--|/\*|\*/)")


class _SafePatientInput(CamelModel):
    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def validate_text(cls, value, info: ValidationInfo):
        if not isinstance(value, str):
            return value
        limit = _TEXT_LIMITS.get(info.field_name, 2000)
        if len(value) > limit or re.search(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f]", value) or _SQL_COMMAND.search(value):
            raise ValueError("Texto no permitido o demasiado largo")
        if info.field_name in {"name", "dni"} and not _SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError("El campo contiene caracteres no permitidos")
        return value


class Patient(CamelModel):
    id: str
    dni: str
    name: str
    age: int | None = None
    gender: str | None = None
    blood_type: str | None = None
    phone: str | None = None
    admission_date: str | None = None
    triage_level: int | None = None
    status: str
    department: str | None = None
    room_number: str | None = None
    bed_id: str | None = None
    doctor_assigned_id: str | None = None
    doctor_assigned_name: str | None = None
    diagnosis: str | None = None
    allergies: str | None = None
    vitals: Vitals = Field(default_factory=Vitals)
    notes: str | None = None
    discharge_date: str | None = None
    discharge_notes: str | None = None
    # Campos adicionales derivados del HIS (no rompen el contrato del frontend)
    admission_class: str | None = None
    admission_route: str | None = None
    main_specialty: str | None = None
    length_of_stay_days: float | None = None
    source: str | None = None


class PatientCreate(_SafePatientInput):
    """Payload de PatientService.create y del wizard de ingreso."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    dni: str = Field(min_length=1)
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = None
    blood_type: str | None = None
    phone: str | None = None
    allergies: str | None = None
    triage_level: int | None = Field(default=4, ge=1, le=5)
    vitals: InputVitals | None = None
    symptoms: str | None = None
    department: str | None = None
    room_number: str | None = None
    bed_id: str | None = None
    doctor_assigned_id: str | None = None
    doctor_assigned_name: str | None = None
    doctor_name: str | None = None
    status: str | None = None
    diagnosis: str | None = None
    notes: str | None = None


class PatientUpdate(_SafePatientInput):
    """PatientService.update envía el objeto completo o parcial."""
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = None
    blood_type: str | None = None
    phone: str | None = None
    allergies: str | None = None
    triage_level: int | None = Field(default=None, ge=1, le=5)
    status: str | None = None
    department: str | None = None
    bed_id: str | None = None
    doctor_assigned_id: str | None = None
    doctor_assigned_name: str | None = None
    diagnosis: str | None = None
    notes: str | None = None
    vitals: InputVitals | None = None
    discharge_date: str | None = None
    discharge_notes: str | None = None
