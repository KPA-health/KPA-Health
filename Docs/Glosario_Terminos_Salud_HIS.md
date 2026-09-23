GLOSARIO DE TÉRMINOS DEL SECTOR SALUD

Guía de apoyo para el Diccionario de Datos HIS — DateBaseHIS.xlsx

Dirigido a equipos de ingeniería de sistemas sin experiencia previa en el sector salud

22 de septiembre de 2026

Este glosario explica, en lenguaje sencillo, los términos y siglas propios del sector salud colombiano que aparecen en el
Diccionario de Datos HIS y en el Diagrama de la Base de Datos HIS. No repite conceptos de modelado de datos (clave
primaria, clave foránea, tipo de dato), que se asumen conocidos por el equipo de ingeniería.

Siglas y sistemas del sector salud

Término / Sigla

Significado en este contexto

HIS

IPS

EPS

ARL

RIPS

CUPS

CIE-10

Sistema de Información Hospitalaria (Hospital Information System): el software que
administra los procesos clínicos y administrativos de una institución de salud — admisiones,
historia clínica, servicios, facturación, etc. El archivo DateBaseHIS.xlsx es un extracto de un
sistema de este tipo.

Institución Prestadora de Servicios de Salud: la entidad (clínica, hospital, centro médico) que
presta directamente los servicios de salud al paciente.

Entidad Promotora de Salud: aseguradora que administra la afiliación de las personas al
sistema de salud colombiano y gestiona su acceso a los servicios. Aparece como valor del
campo Asegurador.

Administradora de Riesgos Laborales: aseguradora que cubre los accidentes de trabajo y las
enfermedades de origen laboral.

Registro Individual de Prestación de Servicios de Salud: el reporte oficial que las IPS deben
enviar al sistema de salud colombiano con el detalle de cada servicio prestado. La estructura
de este archivo es similar a la que alimenta ese reporte.

Clasificación Única de Procedimientos en Salud: catálogo oficial colombiano de códigos para
procedimientos y servicios médicos. Es el tipo de código usado en el campo CodigoServicio
de la tabla Servicios.

Clasificación Internacional de Enfermedades, décima versión: catálogo internacional de
códigos de diagnóstico. Es el tipo de código usado en el campo CodigoDiagnostico de la tabla
Ingresos.

Tipos de documento de identificación (campo TipoDocumento de Paciente)

Término / Sigla

Significado en este contexto

CC

TI

CE

RC

PA

CN

PPT

Cédula de Ciudadanía: documento de identidad estándar para adultos colombianos.

Tarjeta de Identidad: documento de identidad para menores de edad (entre 7 y 17 años) en
Colombia.

Cédula de Extranjería: documento de identidad para extranjeros residentes en Colombia.

Registro Civil de Nacimiento: documento de identidad para niños menores de 7 años.

Pasaporte.

Certificado de Nacido Vivo: documento que identifica a un recién nacido antes de que tenga
registro civil.

Permiso por Protección Temporal: documento que permite a ciudadanos extranjeros
(principalmente venezolanos) acceder a servicios en Colombia.

Término / Sigla

Significado en este contexto

ASI

MSI

DIE

SA

Adulto Sin Identificar: persona adulta atendida sin ningún documento de identidad
disponible.

Menor Sin Identificar: persona menor de edad atendida sin ningún documento de identidad
disponible.

Documento de Identificación Extranjero: variante local del documento de identidad
extranjero, equivalente a la Cédula de Extranjería.

Salvoconducto (de permanencia): documento temporal de identificación para personas en
trámite de regularización migratoria.

Afiliación y aseguramiento en salud

Término / Sigla

Significado en este contexto

Régimen (de afiliación)

La categoría bajo la cual una persona está vinculada al sistema de salud colombiano.
Contributivo: afiliados que cotizan (trabajadores o independientes). Subsidiado: población de
bajos ingresos, afiliada sin cotizar, subsidiada por el Estado. Vinculado: personas sin afiliación
formal, atendidas mientras se les asigna un régimen. Particular: personas que pagan
directamente el servicio, sin pasar por una aseguradora. Otro: cualquier categoría no
clasificada en las anteriores.

Asegurador

La EPS, ARL u otra entidad responsable de pagar o autorizar la atención del paciente.

Proceso de atención

Término / Sigla

Significado en este contexto

Ingreso / Admisión

El registro de un episodio de atención de un paciente en la institución, desde que llega hasta
que es dado de alta. Es el concepto central de la tabla Ingresos; no equivale a una visita al
médico sino a todo el episodio.

Clase de ingreso

Indica si la atención fue Ambulatoria (sin hospitalización) u Hospitalaria (con internación).

Vía de ingreso

El punto de entrada del paciente a la institución: Urgencias, Hospitalización (programada),
Remitido (referido desde otra institución) o Cirugía Ambulatoria.

Tipo de riesgo

Triage

El origen del evento que causó la atención, usado para fines legales y de facturación:
accidente de trabajo, accidente de tránsito, accidente en el hogar, enfermedad general,
enfermedad profesional, atención inicial de urgencias, atención de población perinatal
(madre o recién nacido), evento catastrófico de origen natural, lesión autoinflingida, lesión
por agresión u otro tipo de accidente.

Proceso de clasificación de pacientes en urgencias según la gravedad de su condición clínica,
para decidir quién se atiende primero (no por orden de llegada). En Colombia suele usarse
una escala de 5 niveles, donde Triage I es el más urgente y Triage V el menos urgente.

Motivo de consulta

La razón, en palabras del paciente o del profesional que lo atiende, por la que se solicita la
atención.

Término / Sigla

Significado en este contexto

Diagnóstico (principal)

La condición de salud identificada por el profesional tratante, codificada con CIE-10.

Especialidad (médica)

La rama de la medicina del profesional que prestó el servicio, por ejemplo Medicina General,
Cirugía o Pediatría.

Área de servicio

La unidad funcional de la institución donde se prestó el servicio, por ejemplo Laboratorio
Clínico, Farmacia u Hospitalización.

Programación quirúrgica

El proceso de agendar una cirugía o procedimiento quirúrgico antes de realizarlo. Puede no
coincidir con la ejecución real del procedimiento: una cirugía programada puede no
ejecutarse, y una ejecutada puede no haber sido programada previamente.

Signos vitales (campos de la tabla Triage)

Término / Sigla

Significado en este contexto

Tensión arterial

Presión de la sangre sobre las arterias, expresada como dos números — sistólica/diastólica
—, por ejemplo “120/80”.

Frecuencia cardiaca

Número de latidos del corazón por minuto.

Frecuencia respiratoria

Número de respiraciones por minuto.

Temperatura

Temperatura corporal del paciente, en grados Celsius.

Términos técnicos con un significado propio en este modelo

Término / Sigla

Significado en este contexto

OID (OidIngreso,
OidTriage, OidS, OidMI)

En este archivo NO es el identificador estándar ISO/ASN.1 que suele conocerse en sistemas
distribuidos. Aquí es solo el prefijo que el HIS usa para nombrar sus identificadores
numéricos internos; equivale a un ID autoincremental de base de datos.

Consecutivo

Número secuencial asignado internamente a un registro, de uso administrativo (similar a un
identificador, pero pensado para control interno más que para relacionar tablas).

