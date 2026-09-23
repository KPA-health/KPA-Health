# Implementación de la prueba NL2SQL con hospital.db

Fecha: 23 de septiembre de 2026.

## Resultado

Se implementó una aplicación de prueba funcional con campo de pregunta, selector local/nube, SQL visible, parámetros, estado de ejecución y tabla de resultados. La ruta de prueba llama siempre al modelo elegido: no sustituye la llamada por una plantilla SQL.

Entrada: pregunta en español. Proceso: LLM → plan JSON con SQL → validación → ejecución local de solo lectura → respuesta JSON → tabla y SQL en pantalla.

La aplicación consulta exclusivamente **`hospital.db` en la raíz del proyecto**, independientemente del directorio desde el que se importe el módulo. No usa `hospital_validated.db`, no reimporta los TXT y no modifica datos ni el esquema persistente. Conserva el backend híbrido anterior en `backend/app.py`; la aplicación de prueba se inicia específicamente con `backend.playground:app`.

## Cómo abrirla

Servidor de prueba de esta entrega: **http://127.0.0.1:8001**.

Para iniciarlo de nuevo desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.playground:app --host 127.0.0.1 --port 8001
```

También puedes ejecutar `scripts/start_playground.ps1`. Si el puerto ya está ocupado por esta aplicación, abre la URL existente; no arranques una segunda instancia en el mismo puerto. La instancia antigua de desarrollo del puerto 8000 no es la versión final de esta prueba.

En una instalación nueva, crea el entorno e instala dependencias:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-playground.txt
```

Mantén Ollama iniciado. `qwen3:4b` ya estaba instalado en este equipo; en otro equipo se necesita instalarlo antes. No abras `test_ui.html` con doble clic: la página y la API se sirven desde el mismo origen HTTP.

## Prueba local

1. Abre la URL y deja seleccionado **Local · Qwen3 4B (Ollama)**.
2. Escribe `¿Cuántos ingresos hubo en agosto de 2026?` o usa el botón de ejemplo.
3. Pulsa **Generar SQL y consultar**.
4. Revisa el SQL, la indicación de ejecución, los parámetros y la tabla.

En la prueba real, Qwen generó:

```sql
SELECT SUM(ingresos) AS total_ingresos
FROM consulta_ingresos
WHERE fecha >= '2026-08-01' AND fecha < '2026-09-01'
```

Resultado: **3.622 ingresos**. Se contrastó con un `COUNT(*)` directo sobre `Ingresos` con el mismo intervalo. La ejecución real observada tardó aproximadamente 28 segundos, incluyendo generación. No es una garantía de latencia; el modelo puede producir SQL equivalente distinto.

La vista `consulta_ingresos` es temporal y se deriva directamente de `hospital.db.Ingresos`. Suma los conteos de los grupos, en lugar de confundir el número de grupos con episodios.

## Modelo en la nube

Selecciona **Nube · API compatible con Chat Completions** y completa:

- URL base HTTPS del proveedor, sin `/chat/completions` al final: la aplicación lo agrega.
- Identificador exacto de un modelo disponible en tu cuenta.
- API key, o variable `NL2SQL_CLOUD_API_KEY` en un `.env` local.
- Opcionalmente, modo JSON, temperatura y máximo de tokens. Puedes omitir los dos últimos dejando sus campos vacíos y desactivar el parámetro de modo JSON si tu proveedor no lo admite.

El transporte envía `POST {base_url}/chat/completions`, cabecera `Authorization: Bearer ...`, `messages`, `model` y `stream: false`. Extrae el texto de `choices[0].message.content`. La respuesta debe seguir el contrato JSON incluso si no se solicita `response_format`.

Por ejemplo, Gemini documenta una capa compatible en `https://generativelanguage.googleapis.com/v1beta/openai/`. Selecciona un modelo actualmente habilitado en tu cuenta: esta entrega no fija ni promete disponibilidad de un identificador de nube. Referencia primaria: [compatibilidad de Gemini](https://ai.google.dev/gemini-api/docs/openai).

“Cualquier API” queda acotado al protocolo compatible descrito. Un servicio con cabeceras, autenticación o esquema de mensajes diferentes necesita otro adaptador en `generate()`. Tampoco se garantiza que cualquier modelo genere SQL correcto. Las opciones visibles permiten probar proveedores compatibles sin cambiar código ni reiniciar.

La clave permanece en el campo de contraseña y en memoria durante la solicitud; no se persiste en localStorage ni en archivos por la aplicación. Se transmite del navegador al backend local y de este al proveedor indicado. No se devuelven claves ni cuerpos de error del proveedor. Se envían pregunta y esquema agregado; **no se envían filas de hospital.db** ni se usa una segunda llamada para narrar los resultados. No incluyas datos personales en preguntas enviadas a nube.

La conexión de nube se verificó con transporte simulado. **No se ejecutó una llamada real de pago ni se verificó una API key de nube**, porque no se proporcionó una credencial.

## Configuración local

`.env.example` contiene:

```dotenv
NL2SQL_LOCAL_MODEL=qwen3:4b
NL2SQL_OLLAMA_URL=http://127.0.0.1:11434
NL2SQL_CLOUD_API_KEY=
```

Copia a `.env` si necesitas cambiar valores. Reinicia el servidor al cambiar variables. `.env` está excluido de Git. El modelo local se conecta mediante `/api/chat`, con `think: false`, `stream: false`, temperatura 0, contexto 4096 y máximo 1024 tokens generados. La interfaz y `/api/info` muestran el nombre efectivo configurado en la información de conexión.

Se usa `format: "json"` y validación Pydantic posterior: el runtime instalado devolvió HTTP 400 al intentar construir una gramática para el esquema con diccionario abierto de parámetros. El modo JSON resolvió esa incompatibilidad sin eliminar la validación del contrato. Referencia: [API de Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md).

## Datos, diccionario y alcance semántico

El contexto implementado se deriva de `Docs/Diccionario_Datos_HIS.md`, `Docs/Glosario_Terminos_Salud_HIS.md` y las limitaciones del EDA del proyecto. La aplicación usa una selección fija de estas definiciones; no vectoriza documentos ni interpreta automáticamente cambios posteriores del diccionario.

| Vista temporal | Fuente de hospital.db | Datos expuestos |
|---|---|---|
| `consulta_ingresos` | `Ingresos` | Fecha, vía, clase, grupo de cama histórico y cantidad de episodios |
| `consulta_triage` | `Triage` | Fecha, clasificación original y cantidad de registros |
| `consulta_medicamentos` | `MedicamentoInsumo` | Fecha, código/producto y cantidad dispensada |
| `consulta_servicios` | `Servicios` | Fecha, especialidad, registros y cantidad |

No se exponen pacientes individuales, nombres, documentos, diagnósticos individuales ni motivos de consulta. Los grupos agregados pueden ser pequeños: esto es una prueba local, no una certificación de anonimización o un despliegue hospitalario de producción.

La fecha actual se calcula en `America/Bogota`. Las fechas históricas no se desplazan para aparentar datos actuales. La cabecera muestra el rango observado de ingresos.

La importación original tiene discrepancias documentadas —16.055 filas de Triage frente a 16.106 válidas en el EDA anterior—. Se muestra una advertencia; esta tarea no modifica ni corrige la importación solicitada.

### Caso de camas UCI

`¿Cuántas camas de UCI están ocupadas hoy?` pasa al modelo, pero la base no contiene censo actual ni egresos que permitan reconstruir esa ocupación. El comportamiento correcto es `insufficient_data`, sin ejecutar una consulta de ocupación inventada. La prueba real lo confirmó.

Existe además un control independiente para impedir que una respuesta del modelo que cuente ingresos se presente como ocupación o inventario. Es conservador y se basa en términos de la pregunta; puede abstenerse ante preguntas más amplias. No es un clasificador semántico universal.

Para probar una pregunta que sí devuelve datos utiliza ingresos de agosto, ingresos por vía, clasificaciones de triage o dispensaciones por producto. La referencia a grupos de cama en admisiones expresa historia de ingresos, no camas actualmente ocupadas.

## API

| Método y ruta | Función |
|---|---|
| `GET /` | Vista de prueba |
| `GET /api/info` | Nombre de DB, modelo local y rango de ingresos |
| `POST /api/query` | Generación por LLM, validación y ejecución |
| `GET /docs` | Documentación interactiva FastAPI |

Ejemplo local:

```json
{"question":"Total de ingresos en agosto de 2026","provider":"local"}
```

Ejemplo nube:

```json
{
  "question":"Total de ingresos por vía",
  "provider":"cloud",
  "cloud":{
    "base_url":"https://proveedor.example/v1",
    "model":"modelo-de-tu-cuenta",
    "api_key":"tu-clave",
    "json_mode":true,
    "temperature":0,
    "max_tokens":1024
  }
}
```

Respuesta: `status`, `message`, `sql`, `params`, `executed`, `provider`, `model`, `database`, `columns`, `rows`, `truncated`, `warnings`, `elapsed_ms`. Se muestra el SQL original del modelo incluso si es bloqueado; `executed` distingue una propuesta de una consulta ejecutada. Los parámetros son los devueltos por el modelo, normalizando prefijos `:`; si el SQL usa literales, pueden no ser necesarios para la ejecución.

Estados de negocio: `ok`, `clarify`, `insufficient_data`, `reject`. Errores HTTP: 422 entrada incompleta, 429 consulta concurrente, 502 respuesta/proveedor inválido, 503 conexión no disponible y 504 timeout. La interfaz presenta el error y permite volver a consultar.

## Controles de ejecución

- SQLite `mode=ro`; vistas TEMP solo en la conexión, `query_only=ON`, extensiones deshabilitadas.
- SQLGlot valida una SELECT sobre exactamente una vista autorizada. Rechaza escritura, tablas base, CTE, JOIN, subconsultas, uniones y funciones no autorizadas.
- Authorizer de SQLite restringe lecturas a vistas y sus accesos internos, y limita funciones.
- Parámetros mediante binding; no se interpola texto de usuario en SQL.
- Cancelación de SQL a los 5 segundos mediante progress handler; máximo 200 filas de resultado con indicador de truncamiento.
- Una generación simultánea por proceso; máximo de espera de red 120 segundos y deadline de generación 125 segundos.
- Sin CORS abierto en esta aplicación; peticiones con Origin ajeno se rechazan. Arranque limitado a `127.0.0.1`.
- El navegador dibuja celdas y SQL con `textContent`, sin ejecutar HTML del modelo.

Estas restricciones protegen el acceso; no demuestran que toda consulta semánticamente válida responda perfectamente a cualquier pregunta. Revisa SQL y resultados durante las pruebas.

## Archivos de la entrega

- `backend/playground.py`: aplicación autónoma, contratos, prompts, dos transportes, vistas temporales y ejecutor.
- `test_ui.html`: formulario, configuración de nube, SQL visible y tabla.
- `scripts/start_playground.ps1`: arranque local en puerto 8001.
- `requirements-playground.txt`: dependencias para reproducir la prueba.
- `.env.example` y `.gitignore`: configuración y exclusión de secretos/artefactos.
- `tests/test_playground.py`: pruebas automatizadas.
- `Docs/test_ui_legacy.html`: copia conservada de la vista previa.
- Este documento: alcance, uso, contratos, evidencia y limitaciones.

## Verificación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_playground.py -v
```

Resultado observado: **9 pruebas aprobadas**. Cubren cálculo contra DB original, SQL visible y ejecución real, parámetros con texto malicioso, bloqueos SQL, ocupación incorrecta propuesta por modelo simulado, validación de entrada, origen ajeno y payloads local/nube. Los tests dependen de la DB del proyecto; uno verifica el total conocido de 17.781 ingresos.

Pruebas reales adicionales: Qwen local generó y ejecutó la consulta de agosto con 3.622 ingresos; el caso UCI devolvió datos insuficientes. Las pruebas de integración simuladas no se presentan como evidencia de conectividad real a la nube.

Se verificó el recorrido completo en navegador con agent-browser: botón de ejemplo → generar → SQL visible → tabla con 3.622, en 24,8 segundos en esa ejecución. También se comprobó que seleccionar nube muestra URL, modelo y campo de clave. Se actualizó el grafo local con `graphify update .`, como requieren las instrucciones del workspace.
