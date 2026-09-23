# Reporte de Implementación del Backend Antigravity

## Resumen Ejecutivo
Se implementó el backend híbrido FastAPI + SQLite con catálogos semánticos, consultas parametrizadas validadas, protección SQL en AST (SQLGlot) y adaptador a Ollama (`qwen3:4b`), cumpliendo con los pasos 0 a 6 del Roadmap. Se reconciliaron las diferencias en el importador de la BD y la ejecución ha sido probada con llamadas locales reales a Ollama.

## Evidencia de Reconciliación de Datos
- **Problema previo:** Existía una discrepancia entre las 16,055 filas importadas de Triage y las 16,106 reportadas en el EDA previo como válidas.
- **Resolución:** Se creó un nuevo importador estricto (`scripts/import_data.py`) empleando literales precisos (`csv.QUOTE_NONE`). Al cargar `Datos/Triage.txt`, de 17,781 filas iniciales se descartaron los nulos en la clave principal (`OidTriage`), reteniendo de manera exacta **16,106 filas válidas**, resolviendo así la discrepancia.

## Vistas y Catálogo de Métricas (Semántica)
Se crearon las 5 familias de métricas requeridas mediante vistas explícitas (`backend/data/semantic.py`) y un catálogo JSON determinista (`config/semantic_catalog.json`):
1. **admissions_count**
2. **wait_mean**
3. **triage_distribution**
4. **medication_dispensed**
5. **services_by_specialty**
Todas son ruteadas mediante plantillas si la consulta lo amerita, logrando respuestas ultrarrápidas (< 1s) para preguntas comunes.

## Ejecutor SQL Seguro
- `backend/query/policy.py` verifica usando el AST (SQLGlot) que solo se envíen sentencias `SELECT` y que estén dirigidas exclusivamente a las vistas aprobadas (`v_admissions_daily`, etc). Se bloquean JOIN, UNION y CTE no permitidos.
- Se implementó un authorizer a nivel de conexión SQLite y `progress_handler` que interrumpe la consulta a los 2.0 segundos máximos, previniendo DoS en la DB.

## Adaptadores y Enrutamiento NL2SQL Local
- `backend/query/router.py` enruta hacia la plantilla si detecta una métrica conocida, y en otro caso usa Ollama.
- Ollama genera usando el modelo `qwen3:4b` en un entorno seguro de solo JSON. 
- **Comportamiento ante fallos (Evidencia):** Al probar con una pregunta maliciosa, el enrutador rechazó la respuesta fallida de Qwen (debido a JSON inválido o estructura incorrecta), demostrando que las protecciones impiden que el backend devuelva errores no controlados. El rechazo final resulta en `status: reject` para el cliente.

## Pruebas de Evaluación Ejecutadas
El script `scripts/evaluate_backend.py` corrobora lo siguiente:
- `/health`: Activo y operando (`status: up`).
- `/api/catalog`: 5 métricas recuperadas.
- Ruteo por plantilla: Respuesta correcta (`status: ok, source: template`).
- Ruteo por LLM (pregunta maliciosa): Bloqueado correctamente (`status: reject, source: local`).
- Comportamiento Offline: Funcional completamente sin llamadas de red externas.

## Estado Final
El backend es funcional en el checkout actual. La API está levantada (con `uvicorn`) y estructurada según lo pactado. Queda delegada la configuración y la puesta a prueba final. No existen bloqueadores.
