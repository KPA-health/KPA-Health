"""DTOs de /patients (ver front-kpa/js/services/patientService.js y mockData.js)."""
from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.schemas.common import CamelModel


class Vitals(CamelModel):
    bp: str | None = None
    hr: str | None = None
    temp: str | None = None
    spo2: str | None = None


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


class PatientCreate(CamelModel):
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
    vitals: Vitals | None = None
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


class PatientUpdate(CamelModel):
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
    vitals: Vitals | None = None
    discharge_date: str | None = None
    discharge_notes: str | None = None
