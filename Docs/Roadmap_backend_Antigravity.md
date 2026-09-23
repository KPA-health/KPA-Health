# Roadmap de backend y encargo de implementación a Antigravity

Fecha: 2026-09-23. Estado: diseño listo para implementar; este documento no acredita implementación ni pruebas del backend.

## 1. Decisiones vigentes y contexto recuperado

Implementar **FastAPI + SQLite + catálogo determinista + NL2SQL local con `qwen3:4b`**, con adaptadores configurables para otros modelos locales. Híbrido significa: resolver preguntas conocidas con plantillas verificadas y recurrir al modelo para preguntas nuevas, manteniendo validación independiente antes de ejecutar cualquier SQL. La respuesta y los gráficos se construyen desde resultados reales, sin segunda llamada generativa por defecto.

Esta instrucción sustituye la selección anterior de Qwen3 8B y el respaldo remoto automático. No habilitar nube ni transmitir registros hospitalarios a proveedores. Modelos mayores y SQLCoder son alternativas configurables, no dependencias obligatorias ni descargas automáticas.

El contexto previo disponible se recuperó de estos documentos del proyecto; no se dispone aquí de una transcripción completa de chats anteriores:

- `Docs/Guia_implementacion_agente_NL2SQL.md`: arquitectura híbrida, fórmulas, SQL seguro y evaluación.
- `Docs/Evaluacion_propuestas_triage_RAG_Jev.md` y `Docs/Evidencia_EDA_HIS.json`: evidencia posterior a la recepción de los TXT; prevalece sobre supuestos anteriores sobre datos ausentes.
- `Docs/Analisis_viabilidad_y_hoja_de_ruta.md`: alcance de ocho horas y división inicial del equipo.
- `Docs/Diccionario_Datos_HIS.md` y `Docs/Glosario_Terminos_Salud_HIS.md`: fuentes obligatorias para nombres, relaciones y semántica.
- `Docs/Descripción_Reto_Hackaton.md`: contrato funcional del reto.

No añadir Jev, entrenamiento, vectorización de registros, RAG documental, voz ni reclasificación clínica al camino crítico. El contexto del modelo sale del catálogo semántico derivado de los diccionarios y del esquema realmente validado.

## 2. Estado comprobado y primer riesgo

Repositorio actual: `C:/Users/SC4RD1N4T0/Documents/KPA-hackaton`, rama observada `dev/marlon`. Existe `.venv`, `setup_db.py`, `hospital.db`, `data/` y `Datos/`. Hay cambios previos del usuario, incluidos documentos sin seguimiento y eliminación del README raíz: conservarlos; no ejecutar reset/clean ni restauraciones globales.

Ollama respondió en `http://127.0.0.1:11434/api/tags` e incluyó `qwen3:4b`. Esto confirma instalación, no precisión, latencia ni generación correcta. No se ejecutó el importador durante esta planificación.

Conteos consultados en SQLite en modo solo lectura:

| Tabla | DB actual | EDA fuente previo |
|---|---:|---:|
| Paciente | 14.502 | 14.502 |
| Ingresos | 17.781 | 17.781 |
| Triage | 16.055 | 17.781 físicas; 16.106 válidas |
| Atencion | 17.375 | 17.375 |
| Servicios | 582.357 | 582.357 |
| MedicamentoInsumo | 579.465 | 579.465 |
| ProgramacionCirugia | 12.770 | 13.046 físicas; 276 duplicados completos |

El importador actual borra tablas al iniciarse, usa comillas CSV por defecto, elimina duplicados indiscriminadamente, infiere tipos de códigos y sustituye faltantes por cero o texto. El EDA ya advertía que las comillas deben tratarse literalmente. **La discrepancia de Triage exige reconciliación; la causa exacta todavía no está demostrada.** Los conteos históricos solo son referencia si coinciden los hashes de los archivos actuales.

## 3. Arquitectura y propiedad

```text
POST /api/query y GET /api/kpis
        -> contratos y fechas -> servicio de métricas compartido
             -> catálogo SQL parametrizado (ruta conocida)
             -> contexto semántico -> ModelClient -> NL2SQL (ruta abierta)
        -> política SQL -> ejecutor SQLite solo lectura
        -> resultados + cobertura + corte + advertencias + gráfico declarativo

TXT + diccionario -> importador offline -> DB versionada validada
                                       -> vistas analíticas permitidas
```

Antigravity es propietario de la implementación backend en este checkout: `backend/`, `tests/`, `scripts/`, `config/`, dependencias, ejemplos de configuración y documentación de ejecución. Puede corregir `setup_db.py` para convertirlo en entrada explícita al importador seguro. No modificar los TXT fuente, eliminar la DB actual, implementar un frontend nuevo, publicar, desplegar o hacer push. Crear una DB nueva para la primera carga corregida. Evitar commits con datos, secretos, `.venv` o artefactos grandes.

Estructura propuesta, ajustable sin alterar contratos:

```text
backend/app.py                  # rutas y ciclo de vida
backend/settings.py             # configuración validada
backend/contracts.py            # solicitudes, respuestas, salida del modelo
backend/data/importer.py         # carga y reporte de calidad
backend/data/semantic.py         # catálogo y vistas
backend/query/catalog.py         # cinco familias y SQL parametrizado
backend/query/router.py          # plantillas, aclaraciones, NL2SQL
backend/query/dates.py           # períodos y contexto explícito
backend/query/policy.py          # inspección AST y permisos
backend/query/executor.py        # conexión RO, authorizer y cancelación
backend/models/base.py           # contrato de proveedor
backend/models/ollama.py         # transporte nativo
backend/models/compatible.py     # chat y completion compatibles
backend/query/presenter.py       # texto y especificación de gráfico
config/models.example.yaml
config/semantic_catalog.json
tests/fixtures/                  # datos sintéticos mínimos
scripts/import_data.py
scripts/evaluate_backend.py
```

## 4. Pasos de implementación y aceptación

### Paso 0 — Congelar contratos y preparar ejecución (20 minutos orientativos)

1. Leer los documentos citados y las instrucciones AGENTS aplicables. Registrar versiones reales de Python, SQLite y dependencias; fijar un conjunto reproducible después de instalar y probar.
2. Crear FastAPI, Pydantic, cliente HTTP asíncrono, SQLGlot, lector de configuración y herramientas de prueba con dependencias mínimas. Reutilizar `.venv` si es compatible.
3. Definir configuración, contratos del apartado 6 y pruebas sintéticas antes de llamar al modelo.
4. Añadir exclusiones puntuales de `.env`, credenciales, entorno virtual y DB generadas sin borrar las reglas existentes.

Aceptación: aplicación importable, `/health` accesible y tests ejecutables sin Ollama ni datos privados; configuración inválida falla con error comprensible.

### Paso 1 — Reconciliar importación y diccionarios (75 minutos)

1. Comparar hashes de `data/` y `Datos/` con la evidencia; elegir un directorio fuente explícito, sin concatenarlos. Si difieren, registrar la discrepancia y evitar decidir silenciosamente cuál representa el mismo lote.
2. Leer UTF-8, separador `|`, comillas literales (`QUOTE_NONE` o lector equivalente); comprobar número de campos y encabezados. Preservar códigos como texto, ceros iniciales y NULL reales. Parsear fechas ISO explícitamente y números con validación.
3. Mantener conteos físicos, válidos, vacíos, duplicados y rechazados por tabla. Separar las filas vacías de Triage; no crear pacientes o claves cero. No imprimir nombres ni narrativas en logs o reportes.
4. Aplicar reglas por tabla para duplicados; documentar los 276 duplicados quirúrgicos si persisten. Registrar referencias huérfanas sin inventar filas padre. Separar staging de datos analíticos para conservar evidencia de calidad sin impedir toda la carga por el extracto quirúrgico incompleto.
5. Verificar las 24 correspondencias de `CodigoTriage` con `ClasificacionTriage`; materializar mapa versionado de código, prioridad y circuito con procedencia. Código `01` no implica prioridad I. Dejar códigos desconocidos o contradictorios como desconocidos.
6. Validar relaciones Paciente–Ingresos, Ingresos–Atencion e Ingresos–Triage; marcar discordancias de paciente (cuatro según EDA). Excluir discordancias de segmentaciones por triage y declarar cobertura; no eliminar esos ingresos del total general.
7. Escribir a una DB nueva mediante staging transaccional; publicar solo al terminar las comprobaciones. Recargar el mismo lote debe producir el mismo resultado sin duplicaciones. Un fallo no altera la DB activa. Versionar lote por hashes y versión de transformaciones.

Aceptación: reporte agregado reconcilia el total de filas por tabla y explica toda diferencia frente a EDA; una prueba con comillas literales detecta la regresión; códigos `01` y NULL sobreviven; importación fallida conserva el lote activo. No dar la DB actual por correcta por el simple hecho de abrirse.

### Paso 2 — Vistas y catálogo de métricas (60 minutos)

1. Construir `v_admissions_daily`, `v_wait_daily`, `v_triage_daily`, `v_medication_daily`, `v_services_daily`, con listas explícitas de columnas públicas.
2. Definir catálogo versionado con `metric_id`, nombre, definición, grano, fórmula, unidad, filtros, dimensiones, procedencia y limitaciones.
3. Implementar `admissions_count`, `wait_mean`, `triage_distribution`, `medication_dispensed`, `services_by_specialty` como consultas parametrizadas verificadas.
4. Espera desde ingreso: cohorte por `FechaIngreso`; unir primera atención por `OidIngreso`. Si aparecen varias atenciones, elegir la primera fecha válida mediante regla explícita. No sustituir por tiempo desde triage. Excluir negativos; mostrar válidos, inválidos y sin atención. Media global = suma de minutos / suma de casos válidos.
5. Ingresos cuentan episodios. Medicamentos muestran cantidades dispensadas por producto, sin sumar unidades heterogéneas. Servicios distinguen unidades de episodios únicos; no sumar distintos entre grupos superpuestos. Agregar por separado tablas de detalle antes de combinarlas.
6. Ocupación real de camas, días de inventario y realizadas/programadas deben devolver `insufficient_data` con campos necesarios: censo/capacidad/egresos, existencias y unidades, o fecha/estado quirúrgico, respectivamente.

Aceptación: resultados de fixtures calculados manualmente coinciden; denominador cero devuelve ausencia calculable, no un cero inventado; chat y KPIs usan el mismo servicio; el catálogo permite explicar cada indicador.

### Paso 3 — Ejecutor seguro antes del LLM (60 minutos)

1. Inspeccionar AST con dialecto SQLite. Permitir una sentencia de lectura sobre vistas y columnas del catálogo; funciones y operadores explícitos. Rechazar inicialmente JOIN, CTE, UNION y subconsultas generadas; las plantillas revisadas siguen una ruta identificada y probada.
2. Rechazar DDL/DML, múltiples sentencias, PRAGMA, ATTACH, metadatos, funciones de archivos/extensiones y referencias a tablas individuales. Validar aliases y todos los nodos, no solo la primera palabra.
3. Separar parámetros tipados del SQL y aplicar binding; comprobar nombres, cantidad y concordancia con filtros resueltos. Ningún texto del usuario se interpola como identificador.
4. Usar conexión `mode=ro`, `query_only`, extensiones deshabilitadas y authorizer. Permitir únicamente las lecturas internas necesarias de vistas aprobadas; probar expresamente que la misma tabla base sigue inaccesible de forma directa.
5. Cancelar consultas mediante deadline y progress handler. Limitar tamaño de entrada, longitud SQL, salida y número de grupos; no limitar filas fuente antes de calcular agregados.

Aceptación: batería adversarial impide escritura, lectura individual, evasión por aliases y consultas costosas; una consulta agregada válida funciona bajo los mismos controles. Los errores no revelan registros o rutas internas.

### Paso 4 — Adaptadores de modelos locales (60 minutos)

1. Implementar `ModelClient.generate(request) -> ModelResult`, con timeout, cancelación, modelo/proveedor efectivos, uso si existe, latencia y errores normalizados. El dominio nunca importa clases de Ollama.
2. Soportar Ollama nativo y transporte compatible configurable para chat/completions y completions. Seleccionar capacidad por perfil, no por el nombre comercial del modelo.
3. Para Qwen usar salida JSON validada. Para un modelo SQLCoder orientado a completion, permitir plantilla de prompt versionada y salida SQL simple; el backend construye el sobre tipado y somete el SQL a la misma política. No exigir que todo modelo converse o genere JSON.
4. Validar capacidades: thinking, schema JSON, stop, límites de contexto y parámetros extra. Rechazar configuración incompatible o declarar explícitamente modo alternativo; nunca quitar controles al recibir un error del proveedor.
5. Probar `qwen3:4b` real con esquema sintético primero y después contexto exclusivamente agregado. Registrar digest si disponible. Concurrencia inicial de una generación y cola acotada; liberar recursos al cancelar.

Aceptación: cambiar perfil modifica modelo/host/transporte sin modificar endpoints ni servicio de métricas; pruebas con servidores simulados verifican bodies y normalización; smoke real de Qwen separado de tests simulados. SQLCoder queda marcado como configuración preparada hasta que exista un servidor real y se pruebe.

### Paso 5 — Enrutamiento híbrido y API (75 minutos)

1. Resolver fechas y filtros en código. Zona `America/Bogota`, intervalos `[inicio, fin)`, última semana = siete días completos anteriores. `reference_date` opcional se etiqueta explícitamente como referencia; jamás desplazar hoy al último dato histórico.
2. Buscar intención inequívoca en catálogo/sinónimos de diccionarios. Negaciones, múltiples intenciones y parámetros ambiguos producen aclaración en vez de una coincidencia por palabra clave insegura.
3. Para preguntas abiertas, seleccionar contexto de vistas y definiciones pertinente y dos ejemplos verificados. No incluir filas individuales, nombres, signos vitales o motivos de consulta. El contenido de datos y del usuario no puede ampliar permisos.
4. Parsear salida del modelo y validar contrato, semántica de métrica, filtros y SQL. El hecho de tener SQL válido no prueba que responda la pregunta. Si no puede corroborarse la intención/fórmula, aclarar o abstenerse.
5. Máximo dos intentos LLM totales dentro del deadline; sin reintentos ocultos del cliente. Ollama caído no afecta a plantillas. Una solicitud abierta sin modelo produce indisponibilidad explícita, no una respuesta aproximada de otra métrica.
6. Crear respuesta determinista con resultados, unidad, corte, fuente, cobertura y gráfico declarativo. Mantener historial mínimo de intención/filtros; no memoria persistente ni caché de respuestas en la primera entrega.

Aceptación: cinco familias por plantilla, una pregunta nueva por Qwen, aclaración, dato insuficiente y caída del modelo tienen respuestas diferenciadas; misma pregunta y filtros en chat/dashboard producen iguales valores.

### Paso 6 — Evaluación, rendimiento y entrega (70 minutos)

1. Fixtures sintéticos prueban joins, nulos, fechas, duplicados, triage y medias ponderadas con resultados independientes.
2. Evaluar al menos 50 preguntas españolas reservadas: paráfrasis, límites temporales, negación, multintención, datos faltantes y ataques. Separar ruta plantilla y ruta modelo; comparar respuestas/resultados, no texto SQL.
3. Informar exactitud sobre respuestas aceptadas, cobertura, abstenciones, errores y tamaño de muestra. Objetivos: 100% de referencias de plantillas correctas, >=95% aceptadas correctas y ninguna ejecución no autorizada en la batería; si no se alcanza, documentar y restringir cobertura.
4. Medir p50/p95, arranque frío y modelo caliente, memoria observada y contención. Objetivos iniciales: plantilla <=1 s, LLM caliente <=15 s, SQL <=2 s. No declararlos cumplidos sin medición.
5. Probar modo offline a nivel aplicación (sin llamadas externas; sin cambiar la red del equipo): plantillas siguen operativas; Qwen responde preguntas nuevas con servicio local disponible. Probar además caída de Ollama.
6. Entregar instrucciones PowerShell, comandos de importación/arranque/tests, OpenAPI, configuración de dos transportes y reporte final con archivos, pruebas ejecutadas y bloqueos. No ocultar una prueba real pendiente tras mocks aprobados.

Aceptación: otra persona puede arrancar backend, reproducir cinco consultas, verificar rechazos e intercambiar perfiles. Entregar `Docs/Backend_implementation_report.md` con evidencia. Estas ventanas suman unas siete horas de trabajo estimado más margen; ajustar por evidencia, sin sacrificar validación para afirmar el plazo.

## 5. Configuración completa de conexión e inferencia

Un registro de perfiles configurado por el operador define los modelos disponibles. La API admite solo `model_profile` preconfigurado, nunca URLs, secretos o parámetros arbitrarios enviados por usuarios. Configuración por archivo con sustitución de variables de entorno; validación al inicio. Cambiar de perfil no requiere modificar lógica de negocio.

```yaml
default_profile: qwen_local
profiles:
  qwen_local:
    enabled: true
    provider: ollama
    mode: chat
    base_url: http://127.0.0.1:11434
    model: qwen3:4b
    api_key_env: null
    output_mode: json_schema
    prompt_template: his_json_v1
    capabilities: {thinking: true, json_schema: true}
    generation:
      temperature: 0
      top_p: 0.9
      seed: 42
      context_window: 8192
      max_output_tokens: 768
      stop: []
      thinking: false
      keep_alive: 30m
    transport:
      connect_timeout_s: 2
      read_timeout_s: 15
      retries: 0
      verify_tls: true
    provider_options: {}
  sqlcoder_local:
    enabled: false
    provider: openai_compatible
    mode: completion
    base_url: http://127.0.0.1:8001/v1
    model: REPLACE_WITH_SERVER_MODEL_ID
    api_key_env: LOCAL_MODEL_API_KEY
    output_mode: sql_text
    prompt_template: sqlcoder_sqlite_v1
    capabilities: {thinking: false, json_schema: false}
    generation:
      temperature: 0
      max_output_tokens: 768
      stop: []
    transport: {connect_timeout_s: 2, read_timeout_s: 15, retries: 0, verify_tls: true}
    provider_options: {}
```

SQLCoder es ejemplo deshabilitado: no se afirma que el puerto, identificador, plantilla o dialecto funcionen sin configuración y evaluación. Agregar un modelo mayor servido por Ollama consiste en clonar el perfil y cambiar `model`, presupuestos y capacidades verificadas. Un runtime con protocolo distinto necesita un adaptador: “agnóstico” no implica compatibilidad universal sin contrato de transporte.

Mapeo nativo propuesto: `context_window -> options.num_ctx`, `max_output_tokens -> options.num_predict`, `thinking -> think`, esquema -> `format`; `keep_alive` es campo nativo. En transporte compatible usar sus campos soportados y endpoints según `mode`, sin reenviar opciones nativas a ciegas. Tamaño de contexto puede requerir configuración en el servidor. Registrar configuraciones efectivas sin secretos. `provider_options` es extensión validada por operador; no puede sobrescribir permisos, destino aprobado ni controles del ejecutor.

Configuración de aplicación requerida: ruta DB y directorio fuente; host `127.0.0.1`; puerto backend; CORS explícito; zona horaria; versión de catálogo; deadline total 30 s; límite SQL 2 s; máximo 200 grupos con indicador de truncamiento; límite de pregunta 2.000 caracteres; una generación concurrente; cola máxima 4 y timeout de espera incluido en deadline; máximo dos intentos; allowlist de destinos locales; logs redactados. Secretos solo mediante entorno y nunca en respuestas de configuración. La ampliación a red requiere autenticación/autorización; no exponerla en esta entrega local.

Referencias primarias consultadas para los transportes: [API de Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md), [compatibilidad de endpoints](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx) y [tipos de solicitud](https://github.com/ollama/ollama/blob/main/api/types.go). Antigravity debe contrastar capacidades contra la versión instalada y probar el payload real.

## 6. Contrato HTTP y errores

| Ruta | Contrato |
|---|---|
| `POST /api/query` | Pregunta, filtros tipados, referencia temporal opcional y `model_profile` permitido. |
| `GET /api/kpis` | Período/filtros validados; mismo catálogo y ejecutor que chat. |
| `GET /api/catalog` | Métricas, definiciones, filtros, dimensiones y límites disponibles. |
| `GET /api/models` | Perfiles habilitados y capacidades públicas; sin secretos, rutas privadas ni configuración arbitraria. |
| `GET /health` | Vida del servicio, estado DB/catálogo/modelo y modo degradado; sin generación LLM por consulta de salud. |

Ejemplo de solicitud:

```json
{"question":"¿Cuántos ingresos hubo en agosto de 2026?","model_profile":"qwen_local","filters":{"start":"2026-08-01","end":"2026-09-01"}}
```

Sobre de respuesta: `request_id`, `status` (`ok|clarify|insufficient_data|reject|unavailable`), `message`, `metric_id`, `source` (`template|local|none`), `model_profile`/`model` o null, `filters`, `reference_date`, `timezone`, `dataset_version`, `catalog_version`, `data_cutoff`, `unit`, `columns`, `rows`, `coverage`, `warnings`, `truncated`, `timings_ms`, `chart` opcional. `rows=[]` en estados sin resultado; no inventar ceros. SQL de diagnóstico solo si se habilita para desarrollo, sin valores privados.

Contrato del modelo JSON: `status` (`ok|clarify|insufficient_data|reject`), `sql`, `params`, `metric_id`, `filters`, `unit`, `message`; `sql=null` cuando no es `ok`. El presenter no confía en cifras incluidas en `message`. Para SQL simple, el adaptador normaliza el sobre pero no atribuye semántica no comprobada.

HTTP: 200 para resultados y estados de negocio; 422 para entrada inválida; 429 para saturación; 503 para dependencia necesaria indisponible y 504 para deadline. Errores transportan `request_id`, código estable y mensaje sin detalles sensibles. Si solo Ollama falla, `/health` informa degradación y `/api/kpis` permanece útil.

## 7. Encargo ejecutable y condición de cierre

**Antigravity: comienza la implementación ahora en el checkout indicado y sigue los pasos 0–6.** La tarea es producir el backend funcional, no otro plan. Lee primero los diccionarios y las guías previas, aplicando las decisiones vigentes de este documento ante conflictos. Tienes propiedad exclusiva de las modificaciones backend durante el handoff. Preserva los cambios previos del usuario y los datos fuente. Usa `qwen3:4b` instalado; prepara adaptadores y perfiles intercambiables sin descargar modelos adicionales.

No pares en un esqueleto ni declares éxito si solo pasan mocks. Entrega evidencia de importación reconciliada, métricas correctas, SQL protegido, API híbrida, Qwen real y comportamiento ante fallos. Si un bloqueo impide una parte, termina las independientes y documenta el bloqueo exacto y el requisito pendiente. Mantén informado al usuario desde tu terminal. No se pide despliegue ni publicación.

La entrega de este roadmap y su envío aceptado a Antigravity completa la delegación; no significa que el backend ya esté terminado. Registrar el recibo de envío en un documento separado, sin editar retrospectivamente resultados de implementación.
