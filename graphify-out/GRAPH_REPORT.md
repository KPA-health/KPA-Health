# Graph Report - KPA-hackaton  (2026-09-23)

## Corpus Check
- 31 files · ~33,326,604 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 174 nodes · 232 edges · 20 communities (17 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `33e0866d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- playground.py
- Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev
- ModelResult
- Análisis de viabilidad y hoja de ruta del reto hospitalario
- 4. Pasos de implementación y aceptación
- Guía de implementación: agente hospitalario NL2SQL
- PlaygroundTests
- Reporte de Implementación del Backend Antigravity
- Documentación: Funcionalidad de Frontend NL2SQL e Integración Híbrida
- SemanticCatalog
- import_data.py
- Settings
- Antigravity_handoff_status.md

## God Nodes (most connected - your core abstractions)
1. `ModelResult` - 11 edges
2. `query_endpoint()` - 10 edges
3. `Análisis de viabilidad y hoja de ruta del reto hospitalario` - 10 edges
4. `route_query()` - 9 edges
5. `Guía de implementación: agente hospitalario NL2SQL` - 9 edges
6. `execute_readonly_query()` - 8 edges
7. `PlaygroundTests` - 8 edges
8. `Reporte de Implementación del Backend Antigravity` - 8 edges
9. `Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev` - 8 edges
10. `Roadmap de backend y encargo de implementación a Antigravity` - 8 edges

## Surprising Connections (you probably didn't know these)
- `query_endpoint()` --uses--> `QueryRequest`  [INFERRED]
  backend/app.py → backend/contracts.py
- `query_endpoint()` --uses--> `QueryResponse`  [INFERRED]
  backend/app.py → backend/contracts.py
- `query_endpoint()` --uses--> `PolicyViolationError`  [INFERRED]
  backend/app.py → backend/query/executor.py
- `query_endpoint()` --uses--> `QueryTimeoutError`  [INFERRED]
  backend/app.py → backend/query/executor.py
- `query_endpoint()` --calls--> `route_query()`  [EXTRACTED]
  backend/app.py → backend/query/router.py

## Import Cycles
- None detected.

## Communities (20 total, 3 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.15
Nodes (20): get_catalog(), get_models(), health_check(), kpis_endpoint(), get, post, query_endpoint(), BaseModel (+12 more)

### Community 1 - "playground.py"
Cohesion: 0.17
Nodes (17): Connection, execute(), generate(), index(), info(), local_origin(), Plan, prompt() (+9 more)

### Community 2 - "Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev"
Cohesion: 0.11
Nodes (18): 1. Evidencia nueva y alcance del EDA, 2. Idea 1: EDA más lógica difusa para clasificar triage, 3. Idea 2: RAG para vectorizar información de pacientes, 4. Idea 3: Jev para enrutamiento y voz, 5. Qué no pueden resolver estas tecnologías con los datos actuales, 6. Stack y secuencia recomendados, 7. Evaluación que decidiría la adopción de Jev o de otra capa, Ahorro: condiciones y ejemplo (+10 more)

### Community 3 - "ModelResult"
Cohesion: 0.29
Nodes (9): ModelClient, ModelResult, BaseModel, OllamaClient, OpenAICompatibleClient, generate_template_sql(), load_profiles(), Any (+1 more)

### Community 4 - "Análisis de viabilidad y hoja de ruta del reto hospitalario"
Cohesion: 0.12
Nodes (14): 1. Base del análisis y límites de la evidencia, 2. Análisis de requisitos y contradicciones, 3. Viabilidad profesional, 4.1 Decisión sobre NL2SQL, 4.2 Controles mínimos, 4. Arquitectura recomendada, 5.1 Definiciones de los KPI, 5.2 Recomendaciones y tiempo de referencia (+6 more)

### Community 5 - "4. Pasos de implementación y aceptación"
Cohesion: 0.12
Nodes (15): 1. Decisiones vigentes y contexto recuperado, 2. Estado comprobado y primer riesgo, 3. Arquitectura y propiedad, 4. Pasos de implementación y aceptación, 5. Configuración completa de conexión e inferencia, 6. Contrato HTTP y errores, 7. Encargo ejecutable y condición de cierre, Paso 0 — Congelar contratos y preparar ejecución (20 minutos orientativos) (+7 more)

### Community 6 - "Guía de implementación: agente hospitalario NL2SQL"
Cohesion: 0.17
Nodes (11): 1. Decisión recomendada, 2. Modelos y parámetros iniciales, 3. Datos y capa semántica, 4. Plantillas, contexto y prompt NL2SQL, 5. Ejecución segura y rutas de respaldo, 6. Configuración operativa inicial, 7. Memoria y caché mínima, 8. Aceptación y orden de trabajo (+3 more)

### Community 8 - "Reporte de Implementación del Backend Antigravity"
Cohesion: 0.22
Nodes (8): Adaptadores y Enrutamiento NL2SQL Local, Ejecutor SQL Seguro, Estado Final, Evidencia de Reconciliación de Datos, Pruebas de Evaluación Ejecutadas, Reporte de Implementación del Backend Antigravity, Resumen Ejecutivo, Vistas y Catálogo de Métricas (Semántica)

### Community 9 - "Documentación: Funcionalidad de Frontend NL2SQL e Integración Híbrida"
Cohesion: 0.33
Nodes (5): 1. El Frontend de Prueba (`test_ui.html`), 2. Flexibilidad de Proveedores de IA (Model Profiles), 3. Resolución de la Pregunta NL2SQL de Ejemplo, 4. Instrucciones para la Ejecución, Documentación: Funcionalidad de Frontend NL2SQL e Integración Híbrida

### Community 11 - "import_data.py"
Cohesion: 0.83
Nodes (3): create_schema(), import_table(), main()

### Community 12 - "Settings"
Cohesion: 0.67
Nodes (3): Config, Settings, BaseSettings

## Knowledge Gaps
- **60 isolated node(s):** `Config`, `1. Base del análisis y límites de la evidencia`, `2. Análisis de requisitos y contradicciones`, `3. Viabilidad profesional`, `4.1 Decisión sobre NL2SQL` (+55 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev` connect `Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev` to `Análisis de viabilidad y hoja de ruta del reto hospitalario`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `ModelResult` (e.g. with `OllamaClient` and `OpenAICompatibleClient`) actually correct?**
  _`ModelResult` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `query_endpoint()` (e.g. with `QueryRequest` and `QueryResponse`) actually correct?**
  _`query_endpoint()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Config`, `1. Base del análisis y límites de la evidencia`, `2. Análisis de requisitos y contradicciones` to the rest of the system?**
  _60 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Evaluación de EDA y lógica difusa, RAG y enrutamiento con Jev` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `Análisis de viabilidad y hoja de ruta del reto hospitalario` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Should `4. Pasos de implementación y aceptación` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._