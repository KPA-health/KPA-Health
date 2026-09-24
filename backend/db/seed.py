"""
Datos semilla.

- MAPA_SERVICIO: normaliza NombreGrupoCama del HIS a nombres de servicio
  alineados con los departamentos del frontend (config.js).
- DEMO_DOCTORS / DEMO_APPOINTMENTS: el extracto del HIS no trae personal
  médico ni agenda de citas. Para que los módulos de médicos y citas del
  frontend funcionen contra la API real, se siembran los mismos registros
  ficticios de hospital-spa/js/mockData.js (marcados con Origen = 'Demo').
  Por privacidad, las citas guardan un seudónimo del paciente, nunca su nombre.
"""

MAPA_SERVICIO: list[tuple[str, str]] = [
    ("UNIDAD DE CUIDADO INTENSIVO", "Cuidados Intensivos (UCI)"),
    ("UNIDAD DE CUIDADO INTERMEDIO", "Cuidado Intermedio"),
    ("UNIDAD DE CUIDADO BASICO", "Cuidado Básico Neonatal"),
    ("HOSPITALIZACION", "Hospitalización"),
    ("PEDIATRIA", "Pediatría"),
    ("URGENCIAS", "Urgencias"),
    ("GINECO OBSTRETICIA", "Gineco-Obstetricia"),
    ("RECUPERACION", "Recuperación"),
    ("SALA PARTOS", "Sala de Partos"),
]

DEMO_DOCTORS: list[dict] = [
    {
        "IdMedico": "DOC-101", "Nombre": "Dra. Elena Ramos Morales", "Especialidad": "Cardiología",
        "Departamento": "Cardiología", "RegistroProfesional": "CMP-48291",
        "Turno": "Mañana (07:00 - 15:00)", "Estado": "Disponible", "Telefono": "+34 612 345 678",
        "Email": "e.ramos@medipulse.org", "Consultorio": "Cons. 104 - Ala Este",
        "Avatar": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=200",
    },
    {
        "IdMedico": "DOC-102", "Nombre": "Dr. Carlos Mendoza Soler",
        "Especialidad": "Traumatología y Ortopedia", "Departamento": "Traumatología",
        "RegistroProfesional": "CMP-39104", "Turno": "Tarde (15:00 - 23:00)", "Estado": "En Cirugía",
        "Telefono": "+34 623 456 789", "Email": "c.mendoza@medipulse.org", "Consultorio": "Quirófano Q-02",
        "Avatar": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&q=80&w=200",
    },
    {
        "IdMedico": "DOC-103", "Nombre": "Dra. Sofía Valenzuela Paz",
        "Especialidad": "Cuidados Intensivos (UCI)", "Departamento": "Cuidados Intensivos (UCI)",
        "RegistroProfesional": "CMP-51203", "Turno": "Guardia 24h", "Estado": "En Consulta",
        "Telefono": "+34 634 567 890", "Email": "s.valenzuela@medipulse.org",
        "Consultorio": "UCI Central - Box 3",
        "Avatar": "https://images.unsplash.com/photo-1594824813576-928929949bb7?auto=format&fit=crop&q=80&w=200",
    },
    {
        "IdMedico": "DOC-104", "Nombre": "Dr. Mateo Benítez Rivas", "Especialidad": "Pediatría",
        "Departamento": "Pediatría", "RegistroProfesional": "CMP-29845",
        "Turno": "Mañana (07:00 - 15:00)", "Estado": "Disponible", "Telefono": "+34 645 678 901",
        "Email": "m.benitez@medipulse.org", "Consultorio": "Cons. 201 - Pabellón Infantil",
        "Avatar": "https://images.unsplash.com/photo-1537368910025-700350fe46c7?auto=format&fit=crop&q=80&w=200",
    },
    {
        "IdMedico": "DOC-105", "Nombre": "Dra. Carmen Navarro Gil", "Especialidad": "Neurología",
        "Departamento": "Neurología", "RegistroProfesional": "CMP-60312",
        "Turno": "Mañana (07:00 - 15:00)", "Estado": "Disponible", "Telefono": "+34 656 789 012",
        "Email": "c.navarro@medipulse.org", "Consultorio": "Cons. 305 - Neurociencias",
        "Avatar": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=200",
    },
    {
        "IdMedico": "DOC-106", "Nombre": "Dr. Alejandro Silva Torrico",
        "Especialidad": "Urgencias Médicas", "Departamento": "Urgencias",
        "RegistroProfesional": "CMP-44129", "Turno": "Guardia 24h", "Estado": "Disponible",
        "Telefono": "+34 667 890 123", "Email": "a.silva@medipulse.org",
        "Consultorio": "Triaje de Urgencias",
        "Avatar": "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=200",
    },
]

DEMO_APPOINTMENTS: list[dict] = [
    {
        "IdCita": "APT-501", "IdPacienteApp": "PAC-802", "NombrePaciente": "Paciente PAC-802",
        "IdMedico": "DOC-101", "NombreMedico": "Dra. Elena Ramos Morales", "Especialidad": "Cardiología",
        "Fecha": "2026-09-23", "Hora": "09:00",
        "Motivo": "Ecocardiograma Doppler de control y seguimiento post-crisis",
        "Estado": "Finalizada", "Prioridad": "Urgente",
    },
    {
        "IdCita": "APT-502", "IdPacienteApp": "PAC-804", "NombrePaciente": "Paciente PAC-804",
        "IdMedico": "DOC-102", "NombreMedico": "Dr. Carlos Mendoza Soler",
        "Especialidad": "Traumatología y Ortopedia", "Fecha": "2026-09-23", "Hora": "11:30",
        "Motivo": "Evaluación de herida quirúrgica y control radiológico de fémur",
        "Estado": "En Consulta", "Prioridad": "Normal",
    },
    {
        "IdCita": "APT-503", "IdPacienteApp": "PAC-803", "NombrePaciente": "Paciente PAC-803",
        "IdMedico": "DOC-104", "NombreMedico": "Dr. Mateo Benítez Rivas", "Especialidad": "Pediatría",
        "Fecha": "2026-09-23", "Hora": "16:00",
        "Motivo": "Control espirométrico y ajuste de broncodilatadores",
        "Estado": "Programada", "Prioridad": "Normal",
    },
    {
        "IdCita": "APT-504", "IdPacienteApp": "PAC-805", "NombrePaciente": "Paciente PAC-805",
        "IdMedico": "DOC-105", "NombreMedico": "Dra. Carmen Navarro Gil", "Especialidad": "Neurología",
        "Fecha": "2026-09-24", "Hora": "10:15",
        "Motivo": "Descarte de neuropatía diabética periférica con electromiografía",
        "Estado": "Programada", "Prioridad": "Normal",
    },
    {
        "IdCita": "APT-505", "IdPacienteApp": "PAC-806", "NombrePaciente": "Paciente PAC-806",
        "IdMedico": "DOC-106", "NombreMedico": "Dr. Alejandro Silva Torrico", "Especialidad": "Urgencias",
        "Fecha": "2026-09-24", "Hora": "12:00",
        "Motivo": "Reevaluación de tolerancia oral y alta definitiva",
        "Estado": "Programada", "Prioridad": "Normal",
    },
]
