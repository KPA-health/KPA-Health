DICCIONARIO DE DATOS HIS

DateBaseHIS.xlsx — 7 tablas

22 de septiembre de 2026

Paciente (14.502 filas)

Campo

Tipo de dato

Longitud
máxima

Acepta
nulos

Clave

Descripción

TipoDocumento

IdPaciente

NombrePaciente

FechaNacimiento

Sexo

Asegurador

Regimen

Departamento

Municipio

Zona

texto

entero

texto

fecha

texto

texto

texto

texto

texto

texto

3

6

3

10

9

148

12

18

29

6

No

No

No

No

No

No

No

No

No

No

—

PK

—

—

—

—

—

—

—

—

Tipo de documento de identidad del paciente (CC, TI, CE, RC, PA, etc.).

Identificador único del paciente.

Iniciales o nombre anonimizado del paciente.

Fecha de nacimiento del paciente.

Sexo biológico del paciente (Masculino / Femenino).

Entidad aseguradora (EPS/ARL) a la que está afiliado el paciente.

Régimen de afiliación al sistema de salud.

Departamento de residencia del paciente.

Municipio de residencia del paciente.

Zona de residencia (Urbana / Rural).

Ingresos (17.781 filas)

Campo

Tipo de dato

Longitud
máxima

Acepta
nulos

Clave

Descripción

OidIngreso

entero

ConsecutivoIngreso

entero

IdPaciente

entero

ClaseIngreso

ViaIngreso

TipoRiesgo

texto

texto

texto

FechaIngreso

fecha/hora

FechaHospitalizacion

fecha/hora

OidTriageA

CodigoCama

NombreCama

entero

texto

texto

NombreGrupoCama

texto

NombreSubgrupoCa
ma

texto

CodigoDiagnostico

texto

7

7

6

12

20

37

19

19

7

8

50

28

39

4

NombreDiagnostico

texto

173

No

No

No

No

No

No

No

Sí

Sí

No

No

No

No

Sí

Sí

PK

—

Identificador único de la admisión o episodio de atención.

Número consecutivo interno asignado a la admisión.

FK → Paciente

Paciente al que corresponde la admisión.

—

—

—

—

—

Clase de ingreso (Ambulatorio u Hospitalario).

Vía por la que el paciente ingresó a la institución.

Tipo de riesgo u origen del evento que motivó el ingreso.

Fecha y hora en que se registró el ingreso.

Fecha y hora en que se efectuó la hospitalización.

FK → Triage

Evento de triage asociado a la admisión.

—

—

—

—

—

—

Código de la cama asignada.

Nombre o descripción de la cama.

Grupo de camas al que pertenece la cama asignada.

Subgrupo de camas al que pertenece la cama asignada.

Código CIE-10 del diagnóstico principal.

Descripción del diagnóstico principal.

Triage (17.781 filas)

Campo

Tipo de dato

Longitud
máxima

Acepta
nulos

Clave

Descripción

OidTriage

entero

FechaTriage

fecha/hora

MotivoConsulta

TensionArterial

texto

texto

FrecuenciaCardiaca

texto

FrecuenciaRespirator
ia

Temperatura

IdPaciente2

CodigoTriage

ClasificacionTriage

texto

texto

entero

texto

texto

7

19

2564

8

4

4

5

6

2

58

Sí

Sí

Sí

Sí

Sí

Sí

Sí

Sí

Sí

Sí

PK

—

—

—

—

—

—

Identificador único del evento de triage.

Fecha y hora en que se realizó el triage.

Descripción del motivo de consulta registrado en el triage.

Tensión arterial del paciente al momento del triage.

Frecuencia cardiaca del paciente, en latidos por minuto.

Frecuencia respiratoria del paciente, en respiraciones por minuto.

Temperatura corporal del paciente, en grados Celsius.

FK → Paciente

Paciente al que corresponde el triage.

—

—

Código de la categoría de clasificación de triage.

Descripción de la clasificación o prioridad asignada en el triage.

Atencion (17.375 filas)

Campo

Tipo de dato

Longitud
máxima

Acepta
nulos

Clave

Descripción

OidIngreso

entero

FechaAtencion

fecha/hora

7

19

No

No

PK, FK →
Ingresos

—

Admisión a la que corresponde el registro de atención.

Fecha y hora de la primera atención médica.

Servicios (582.357 filas)

Campo

OidS

OidIngreso

CodigoServicio

NombreServicio

Cantidad

entero

entero

texto

texto

entero

FechaPrestacion

fecha/hora

CodigoAreaServicio

texto

AreaServicio

Especialidad

texto

texto

Tipo de dato

Longitud
máxima

Acepta
nulos

6

7

10

252

3

19

5

65

36

No

No

No

No

No

No

No

No

No

Clave

PK

Descripción

Identificador único de la línea de servicio prestado.

FK → Ingresos

Admisión a la que pertenece el servicio.

—

—

—

—

—

—

—

Código del servicio o procedimiento (CUPS).

Descripción del servicio o procedimiento.

Cantidad de unidades del servicio prestadas.

Fecha y hora en que se prestó el servicio.

Código del área hospitalaria que prestó el servicio.

Nombre del área hospitalaria que prestó el servicio.

Especialidad médica que ordenó el servicio.

MedicamentoInsumo (579.465 filas)

Tipo de dato

Longitud
máxima

Acepta
nulos

Campo

OidMI

OidIngreso

CodigoServicio

NombreServicio

Cantidad

entero

entero

texto

texto

entero

FechaPrestacion

fecha/hora

AreaServicio

Especialidad

texto

texto

6

7

15

300

5

19

58

36

No

No

No

No

No

No

No

No

Clave

PK

Descripción

Identificador único de la línea de medicamento o insumo dispensado.

FK → Ingresos

Admisión a la que pertenece el consumo.

—

—

—

—

—

—

Código del medicamento o insumo dispensado.

Descripción del medicamento o insumo dispensado.

Cantidad dispensada.

Fecha y hora en que se dispensó el medicamento o insumo.

Área que realizó la dispensación (farmacia, UCI, etc.).

Especialidad médica que prescribió el medicamento o insumo.

ProgramacionCirugia (13.046 filas)

Campo

Tipo de dato

Longitud
máxima

Acepta
nulos

Clave

Descripción

ConsecutivoProgram
acion

IdPaciente

OidIngreso

CodigoServicio

texto

entero

entero

texto

20

6

7

6

No

No

Sí

No

—

Número de la programación quirúrgica; agrupa los servicios de una misma cirugía.

FK → Paciente

Paciente para quien se programó la cirugía.

FK → Ingresos

Admisión asociada a la cirugía programada.

—

Código del servicio quirúrgico programado.

