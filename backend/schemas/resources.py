"""Contratos de /doctors, /appointments, /rooms, /pharmacy y /stats (ver apiClient.js y mockData.js)."""
from __future__ import annotations

from pydantic import ConfigDict, Field

from backend.schemas.common import CamelModel

# ------------------------------- Médicos -------------------------------------


class Doctor(CamelModel):
    id: str
    name: str
    specialty: str | None = None
    department: str | None = None
    license_number: str | None = None
    shift: str | None = None
    status: str | None = None
    phone: str | None = None
    email: str | None = None
    consulting_room: str | None = None
    avatar: str | None = None


class DoctorUpdate(CamelModel):
    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    shift: str | None = None
    consulting_room: str | None = None
    phone: str | None = None
    email: str | None = None


# -------------------------------- Citas --------------------------------------


class Appointment(CamelModel):
    id: str
    patient_id: str | None = None
    patient_name: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    specialty: str | None = None
    date: str | None = None
    time: str | None = None
    reason: str | None = None
    status: str
    priority: str


class AppointmentCreate(CamelModel):
    model_config = ConfigDict(extra="ignore")

    patient_id: str | None = None
    patient_name: str = Field(min_length=1)
    doctor_id: str | None = None
    doctor_name: str = Field(min_length=1)
    specialty: str | None = None
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = None
    reason: str | None = None
    status: str | None = None
    priority: str | None = None


class AppointmentUpdate(CamelModel):
    model_config = ConfigDict(extra="ignore")

    patient_id: str | None = None
    patient_name: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    specialty: str | None = None
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = None
    reason: str | None = None
    status: str | None = None
    priority: str | None = None


# ------------------------------ Camas ----------------------------------------


class Bed(CamelModel):
    id: str
    code: str
    status: str
    patient_id: str | None = None
    patient_name: str | None = None
    type: str | None = None
    occupied_since: str | None = None


class Wing(CamelModel):
    wing: str
    floor: str
    code: str
    beds: list[Bed]


class BedStatusUpdate(CamelModel):
    model_config = ConfigDict(extra="ignore")

    bed_id: str
    status: str | None = None
    patient_id: str | None = None
    patient_name: str | None = None


# ----------------------------- Farmacia --------------------------------------


class PharmacyItem(CamelModel):
    id: str
    name: str
    generic: str | None = None
    category: str | None = None
    stock: float
    min_stock: float
    unit: str | None = None
    batch: str | None = None
    expiry: str | None = None
    status: str
    daily_consumption: float | None = None
    days_of_inventory: float | None = None
    simulated_stock: bool = True


class PharmacyUpdate(CamelModel):
    model_config = ConfigDict(extra="ignore")

    stock: float | None = Field(default=None, ge=0)
    min_stock: float | None = Field(default=None, ge=0)
    batch: str | None = None
    expiry: str | None = None
    unit: str | None = None


# ---------------------------- Estadísticas -----------------------------------


class Stats(CamelModel):
    active_patients: int
    critical_patients: int
    total_beds: int
    occupied_beds: int
    free_beds: int
    occupancy_rate: int
    today_appointments: int
    available_doctors: int
    critical_meds: int
    # KPIs adicionales para el dashboard hospitalario
    maintenance_beds: int = 0
    reference_date: str | None = None
    avg_wait_minutes_last_7_days: float | None = None
    admissions_on_reference_date: int = 0
    low_stock_meds: int = 0
