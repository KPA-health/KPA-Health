"""
Catálogo semántico para el agente NL2SQL.

Única fuente de verdad de:
- qué tablas/vistas puede consultar el agente (ALLOWED_TABLES),
- qué columnas nunca puede leer (FORBIDDEN_COLUMNS, datos personales),
- la descripción del esquema que se inyecta en el prompt.
El validador (sql_guard) y el authorizer de SQLite (executor) leen de aquí.
"""
from __future__ import annotations

from backend.db.seed import MAPA_SERVICIO

SEMANTIC_VIEWS = (
    "FechaReferencia", "VistaIngresos", "EstadoCamas", "OcupacionDiaria", "EsperaUrgencias",
    "InventarioFarmacia", "CirugiasProgramadas", "CatalogoCamas", "Medico", "Cita",
)
RAW_TABLES = (
    "Ingresos", "Servicios", "MedicamentoInsumo", "Atencion", "Triage", "Paciente",
    "ProgramacionCirugia",
)
ALLOWED_TABLES = frozenset(t.lower() for t in SEMANTIC_VIEWS + RAW_TABLES)

# (tabla, columna) que el agente no puede leer directamente: identifican a una
# persona o son texto clínico libre.
FORBIDDEN_COLUMNS = frozenset({
    ("paciente", "nombrepaciente"),
    ("paciente", "tipodocumento"),
    ("paciente", "fechanacimiento"),
    ("triage", "motivoconsulta"),
    ("cita", "nombrepaciente"),
    ("cita", "idpacienteapp"),
    ("medico", "nombre"),
    ("medico", "registroprofesional"),
    ("medico", "telefono"),
    ("medico", "email"),
    ("medico", "avatar"),
    ("cita", "nombremedico"),
})
FORBIDDEN_COLUMN_NAMES = frozenset(col for _, col in FORBIDDEN_COLUMNS)
TABLES_WITH_PERSONAL_DATA = frozenset({"paciente", "triage", "cita", "medico"})

SERVICE_VALUES = ", ".join(f"'{service}'" for _, service in MAPA_SERVICIO)

SCHEMA_DESCRIPTION = f"""
VISTAS SEMÁNTICAS (úsalas primero):

FechaReferencia(Fecha, Momento)
  1 fila. Es el "HOY" del sistema = fecha del último dato cargado. Fecha 'YYYY-MM-DD'.

VistaIngresos  -- 1 fila por ingreso hospitalario (admisión de un paciente)
  OidIngreso, IdPaciente, Origen ('HIS'|'App'), Sexo ('Femenino'|'Masculino'), Edad (años),
  Regimen, Asegurador, Municipio, Zona, ClaseIngreso ('Hospitalario'|'Ambulatorio'),
  ViaIngreso ('Urgencias'|'Cirugia Ambulatorias'|'Remitido'), TipoRiesgo,
  FechaIngreso, FechaHospitalizacion, FechaInicioEstancia, FechaFinEstimada (egreso estimado),
  Servicio, SubgrupoCama, CodigoCama, NombreCama, CamaVirtual (1 = cama virtual),
  CodigoDiagnostico (CIE-10), NombreDiagnostico (MAYÚSCULAS), FechaTriage, ClasificacionTriage,
  NivelTriage (1 = resucitación ... 5 = no urgente), TurnoIngreso ('Mañana'|'Tarde'|'Noche'),
  EspecialidadPrincipal, Estado ('Crítico'|'Internado'|'En Observación'|'Dado de Alta'),
  Activo (1 = sigue hospitalizado a la fecha de referencia), DiasEstancia
  Valores de Servicio: {SERVICE_VALUES}

EstadoCamas  -- 1 fila por cama física; estado ACTUAL (a la fecha de referencia)
  CodigoCama, NombreCama, Servicio, GrupoCama, SubgrupoCama,
  Estado ('Ocupada'|'Libre'|'Desinfección'|'Mantenimiento'), OidIngreso, IdPaciente, OcupadaDesde

OcupacionDiaria  -- histórico diario de ocupación de camas por servicio
  Fecha, Servicio, CamasTotales, CamasOcupadas, PorcentajeOcupacion (0-100)

EsperaUrgencias  -- 1 fila por ingreso con triage y primera atención médica
  OidIngreso, IdPaciente, ViaIngreso, Servicio, ClasificacionTriage, NivelTriage, FechaTriage,
  FechaAtencion, Fecha (día del triage), Turno ('Mañana'|'Tarde'|'Noche'),
  MinutosEspera (minutos desde el triage hasta la primera atención)

InventarioFarmacia  -- 1 fila por medicamento o insumo
  CodigoMedicamento, NombreMedicamento (MAYÚSCULAS), Categoria, ConsumoTotal, ConsumoUltimos30Dias,
  ConsumoDiarioPromedio, StockActual, StockMinimo, DiasInventario (días de cobertura del stock),
  Estado ('Crítico'|'Bajo'|'Adecuado'), Lote, FechaVencimiento, StockSimulado (1 = stock simulado)
  Categoria incluye: 'Dispositivo médico', 'Antiinfecciosos (antibióticos)',
  'Sistema nervioso (analgésicos, sedantes)', 'Sistema respiratorio', 'Sistema cardiovascular'...

CirugiasProgramadas  -- 1 fila por programación quirúrgica
  ConsecutivoProgramacion, OidIngreso, IdPaciente, NumeroProcedimientos,
  EstadoCirugia ('Realizada'|'No realizada'|'Sin ingreso en el periodo'), FechaCirugia, Fecha,
  AreaQuirofano, Servicio

CatalogoCamas(CodigoCama, NombreCama, GrupoCama, SubgrupoCama, Servicio)  -- camas físicas

Medico  -- personal médico (por privacidad NO se pueden consultar nombres ni registros profesionales)
  IdMedico, Especialidad, Departamento, Turno,
  Estado ('Disponible'|'En Consulta'|'En Cirugía'|...), Consultorio

Cita  -- agenda de citas: IdCita, IdMedico, Especialidad, Fecha, Hora, Motivo,
  Estado ('Programada'|'En Consulta'|'Finalizada'|...), Prioridad ('Normal'|'Urgente')

TABLAS CRUDAS DEL HIS (solo si las vistas no alcanzan; texto en MAYÚSCULAS; texto vacío = 'No Registrado'):
Ingresos(OidIngreso, IdPaciente, ClaseIngreso, ViaIngreso, TipoRiesgo, FechaIngreso,
  FechaHospitalizacion, OidTriageA, CodigoCama, NombreCama, NombreGrupoCama, NombreSubgrupoCama,
  CodigoDiagnostico, NombreDiagnostico)
Servicios(OidS, OidIngreso, CodigoServicio, NombreServicio, Cantidad, FechaPrestacion,
  CodigoAreaServicio, AreaServicio, Especialidad)  -- procedimientos, laboratorios, consultas prestadas.
  Especialidad ej.: 'MEDICINA GENERAL', 'PEDIATRA', 'MEDICINA INTERNA', 'ORTOPEDIA Y TRAUMATOLOGIA',
  'CIRUGIA GENERAL', 'GINECOLOGIA Y OBSTETRICIA'. AreaServicio de quirófanos empieza por 'QUIROFANOS'.
MedicamentoInsumo(OidMI, OidIngreso, CodigoServicio, NombreServicio, Cantidad, FechaPrestacion,
  AreaServicio, Especialidad)  -- cada dispensación de medicamento o insumo (consumo real)
Atencion(IdAtencion, OidIngreso, FechaAtencion)
Triage(OidTriage, FechaTriage, TensionArterial, FrecuenciaCardiaca, FrecuenciaRespiratoria,
  Temperatura, IdPaciente2, CodigoTriage, ClasificacionTriage)
Paciente(IdPaciente, Sexo, Asegurador, Regimen, Departamento, Municipio, Zona)
ProgramacionCirugia(IdProgramacion, ConsecutivoProgramacion, IdPaciente, OidIngreso, CodigoServicio)
""".strip()

# (pregunta, SQL esperado o 'NULL', explicación, categoría)
FEW_SHOT_EXAMPLES: list[tuple[str, str, str, str]] = [
    (
        "¿Cuántas camas de UCI están ocupadas hoy?",
        "SELECT SUM(CASE WHEN Estado = 'Ocupada' THEN 1 ELSE 0 END) AS camas_ocupadas, "
        "COUNT(*) AS camas_totales, "
        "ROUND(100.0 * SUM(CASE WHEN Estado = 'Ocupada' THEN 1 ELSE 0 END) / COUNT(*), 1) AS porcentaje_ocupacion "
        "FROM EstadoCamas WHERE Servicio = 'Cuidados Intensivos (UCI)'",
        "Cuenta las camas físicas de UCI ocupadas y totales a la fecha de referencia.",
        "hospital",
    ),
    (
        "¿Cuáles son los medicamentos con menos de 5 días de inventario?",
        "SELECT CodigoMedicamento, NombreMedicamento, StockActual, ConsumoDiarioPromedio, DiasInventario "
        "FROM InventarioFarmacia WHERE DiasInventario < 5 ORDER BY DiasInventario LIMIT 50",
        "Lista los medicamentos cuyo stock cubre menos de 5 días de consumo promedio.",
        "hospital",
    ),
    (
        "¿Cuál es el tiempo de espera promedio en urgencias en la última semana?",
        "SELECT ROUND(AVG(MinutosEspera), 1) AS espera_promedio_min, COUNT(*) AS pacientes_atendidos "
        "FROM EsperaUrgencias WHERE ViaIngreso = 'Urgencias' "
        "AND Fecha > DATE((SELECT Fecha FROM FechaReferencia), '-7 days') "
        "AND Fecha <= (SELECT Fecha FROM FechaReferencia)",
        "Promedia los minutos entre el triage y la primera atención en urgencias de los últimos 7 días.",
        "hospital",
    ),
    (
        "¿Qué servicio tiene más pacientes ingresados este mes?",
        "SELECT Servicio, COUNT(*) AS ingresos FROM VistaIngresos "
        "WHERE strftime('%Y-%m', FechaIngreso) = strftime('%Y-%m', (SELECT Fecha FROM FechaReferencia)) "
        "GROUP BY Servicio ORDER BY ingresos DESC LIMIT 10",
        "Cuenta los ingresos del mes de referencia agrupados por servicio.",
        "hospital",
    ),
    (
        "Pacientes en triaje crítico (Nivel 1 y 2)",
        "SELECT OidIngreso, IdPaciente, NivelTriage, Servicio, NombreDiagnostico, FechaIngreso, Estado "
        "FROM VistaIngresos WHERE Activo = 1 AND NivelTriage IN (1, 2) "
        "ORDER BY NivelTriage, FechaIngreso DESC LIMIT 50",
        "Lista los pacientes hospitalizados activos con triage nivel 1 o 2.",
        "hospital",
    ),
    (
        "Médicos especialistas disponibles en guardia",
        "SELECT IdMedico, Especialidad, Turno, Consultorio FROM Medico "
        "WHERE Estado = 'Disponible' ORDER BY Especialidad",
        "Lista los médicos disponibles por especialidad, turno y consultorio (sin nombres).",
        "hospital",
    ),
    (
        "¿Qué porcentaje de las cirugías programadas se realizó?",
        "SELECT EstadoCirugia, COUNT(*) AS programaciones, "
        "ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS porcentaje "
        "FROM CirugiasProgramadas WHERE EstadoCirugia <> 'Sin ingreso en el periodo' "
        "GROUP BY EstadoCirugia",
        "Distribuye las programaciones quirúrgicas con ingreso en el periodo según se realizaron o no.",
        "hospital",
    ),
    (
        "¿Cuántas cirugías programadas se realizaron frente a las no realizadas?",
        "SELECT SUM(CASE WHEN EstadoCirugia = 'Realizada' THEN 1 ELSE 0 END) AS cirugias_realizadas, "
        "SUM(CASE WHEN EstadoCirugia = 'No realizada' THEN 1 ELSE 0 END) AS cirugias_no_realizadas, "
        "ROUND(100.0 * SUM(CASE WHEN EstadoCirugia = 'Realizada' THEN 1 ELSE 0 END) / COUNT(*), 1) AS porcentaje_realizadas "
        "FROM CirugiasProgramadas WHERE EstadoCirugia <> 'Sin ingreso en el periodo'",
        "Cuenta las cirugías realizadas y no realizadas y el porcentaje de cumplimiento.",
        "hospital",
    ),
    (
        "Ocupación promedio mensual de camas por servicio",
        "SELECT strftime('%Y-%m', Fecha) AS mes, Servicio, "
        "ROUND(AVG(CamasOcupadas), 1) AS camas_ocupadas_promedio, "
        "ROUND(AVG(PorcentajeOcupacion), 1) AS ocupacion_promedio_pct FROM OcupacionDiaria "
        "GROUP BY mes, Servicio ORDER BY mes, ocupacion_promedio_pct DESC",
        "Promedia por mes y servicio la ocupación diaria estimada de camas.",
        "hospital",
    ),
    (
        "Top 10 medicamentos de mayor rotación este mes",
        "SELECT CodigoServicio AS codigo, NombreServicio AS medicamento, "
        "SUM(Cantidad) AS unidades_dispensadas, COUNT(DISTINCT OidIngreso) AS pacientes "
        "FROM MedicamentoInsumo "
        "WHERE FechaPrestacion >= strftime('%Y-%m-01', (SELECT Fecha FROM FechaReferencia)) "
        "GROUP BY CodigoServicio, NombreServicio ORDER BY unidades_dispensadas DESC LIMIT 10",
        "Suma las unidades dispensadas por medicamento desde el inicio del mes de referencia.",
        "hospital",
    ),
    (
        "¿Cuáles son las especialidades más solicitadas?",
        "SELECT Especialidad, COUNT(DISTINCT OidIngreso) AS pacientes_atendidos, COUNT(*) AS servicios_prestados "
        "FROM Servicios WHERE Especialidad <> 'No Registrado' GROUP BY Especialidad "
        "ORDER BY pacientes_atendidos DESC LIMIT 10",
        "Cuenta pacientes atendidos y servicios prestados por especialidad.",
        "hospital",
    ),
    (
        "Dame el nombre y documento de los pacientes de la UCI",
        "NULL",
        "No está permitido consultar datos personales.",
        "datos_personales",
    ),
    (
        "¿Cómo estará el clima mañana en Popayán?",
        "NULL",
        "La pregunta no trata sobre la operación del hospital.",
        "fuera_de_alcance",
    ),
    (
        "¿Qué opinas de las reformas del gobierno?",
        "NULL",
        "La pregunta no trata sobre la operación del hospital.",
        "fuera_de_alcance",
    ),
    (
        "How many patients are in the ICU?",
        "NULL",
        "La pregunta no está escrita en español.",
        "idioma_no_soportado",
    ),
]
