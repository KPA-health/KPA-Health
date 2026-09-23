# Documentación: Funcionalidad de Frontend NL2SQL e Integración Híbrida

Esta documentación describe la implementación realizada para soportar un entorno de consulta en lenguaje natural (NL2SQL) que permite seleccionar de manera dinámica qué proveedor de Inteligencia Artificial (local o en la nube) se debe utilizar.

## 1. El Frontend de Prueba (`test_ui.html`)
Se agregó un archivo `test_ui.html` que expone un formulario sencillo:
- Un **campo de texto libre** donde el usuario ingresa su pregunta clínica (ej: *"¿cuántas camas de uci están ocupadas hoy?"*).
- Un **menú desplegable (select)** que permite elegir qué perfil de modelo procesará la pregunta.
- Una **tabla de resultados** dinámica donde se renderea la salida procesada del LLM, junto con información sobre el "Source" (es decir, si el backend usó una plantilla pre-aprobada rápida o si el motor pasó por el LLM en caso de ser una métrica no mapeada directamente).

Este frontend es completamente desacoplado y únicamente requiere que el backend `FastAPI` esté corriendo en el puerto 8000.

## 2. Flexibilidad de Proveedores de IA (Model Profiles)
El backend fue desarrollado con el patrón "Agnostic Model Client". Las conexiones al LLM se basan puramente en el archivo de configuración `config/models.yaml`.

- **Modelo Local (Qwen 3:4b):** Configurado bajo el perfil `qwen_local`, usa el cliente HTTP contra un proceso Ollama (`127.0.0.1:11434`). Permite inferencia privada para las preguntas libres generadas por los médicos sin exponer la metadata.
- **Modelos en la Nube (OpenAI / Gemini vía Endpoint Compatible):** El backend ya provee soporte a la nube mediante la clase `OpenAICompatibleClient` añadida en `backend/models/openai_compatible.py`. Cualquier API en la nube que cumpla con el estándar de OpenAI se puede inyectar. Basta con definir un perfil (ej. `openai_online`) en el archivo `.yaml`, indicar la URL (como `https://api.openai.com/v1`) y crear una variable de entorno con la API Key (`OPENAI_API_KEY`). El usuario puede conmutar entre su máquina y un LLM poderoso de forma inmediata desde el desplegable del frontend.

## 3. Resolución de la Pregunta NL2SQL de Ejemplo
**Escenario solicitado:** *"Cuantas camas de uci están ocupadas hoy"*

Para que el LLM local o nube pudiera analizar camas en la base de datos sin requerir escrituras (lo cual la API del ejecutor bloquea por seguridad), se tomó la decisión de:
1. **Modificar el Esquema Semántico:** Se sobre-escribió y recompiló la vista principal `v_admissions_daily` agregando las siguientes dimensiones directamente obtenidas de los ingresos hospitalarios:
   - `bed_code`
   - `bed_name`
   - `bed_group` (Ej: UCI)
   - `bed_subgroup`
2. **Exposición al LLM:** Estos campos fueron indexados en el archivo `config/semantic_catalog.json` para que el prompt del LLM comprenda qué tablas y campos tiene permitido leer al generar el SQL (NL2SQL).
3. **Ejecución y Presentación:** Cuando la consulta llega vía `/api/query`, el enrutador manda la pregunta y la estructura a Ollama (o la nube). Ollama responde con el SQL (`SELECT bed_group, count(*) ...`). Seguidamente, el SQL se interroga mediante un `Abstract Syntax Tree` de SQLGlot asegurando de manera obligatoria que la orden no modifique nada y apunte **solo** a la vista permitida. Si es validado, extrae los datos y retorna al HTML.

## 4. Instrucciones para la Ejecución
1. Iniciar el backend con el entorno activo en la raíz del proyecto:
   ```bash
   uvicorn backend.app:app --host 127.0.0.1 --port 8000
   ```
2. Abrir en cualquier navegador el archivo `test_ui.html`
3. Ingresar la consulta, escoger el modelo, pulsar consultar, y los datos junto al análisis aparecerán expuestos visualmente.
