## Flujo ABSA + Grafo de Conocimiento — Estado del Proyecto

### Resumen
- Proyecto: Análisis de sentimientos basado en aspectos (ABSA) y grafos de conocimiento en contexto educativo.
- Objetivo: Identificar aspectos en comentarios estudiantiles y representarlos en un grafo estructurado (SKOS + propiedades educativas) para análisis y decisiones.

### Flujo propuesto (resumen)
1) Comentarios estudiantiles (CSV/JSON/XLS)
2) Limpieza y normalización
3) Grafo base de conocimiento (SKOS)
4) Ontología educativa (schema)
5) Enriquecimiento de embeddings
6) Modelo ABSA (entrenamiento)
7) Salidas: aspectos, polaridad, entidades vinculadas
8) Tripletas SPO
9) Grafo enriquecido
10) Validación
11) Resultado modelo / análisis

### Estado por etapa
- 1) Ingesta de datos — COMPLETADO
  - Datos globales unificados en `data/exports/global_*.csv`.

- 2) Limpieza y normalización — COMPLETADO
  - Script: `src/preprocessing/cleaning_pipeline.py`.
  - Salida: `data/processed/cleaned_comments.csv` (105,603 filas) + `data/exports/cleaning_report.txt`.
  - Validación: sin duplicados, sin textos vacíos, fechas imputadas.

- 3) Grafo base (SKOS) — COMPLETADO (versión actual)
  - Script: `src/graph_construction/skos_builder.py`.
  - Salidas: `data/exports/skos_nodes.csv`, `skos_edges.csv`, `skos_annotations.csv`, `sample_skos.ttl`, `ontology_aspects.json`.
  - Implementado: ConceptSchemes (`courseBase`, `courseEdition`, `thread`, `comment`, `aspect`, `polarity`), jerarquía (`broader`) y `replyTo` (`related`).
  - **Ontología de aspectos educativos**: 8 aspectos (General, Contenido, Videos, Evaluacion, Retos, Tutoria, Plataforma, Foros) con jerarquías y relaciones semánticas.
  - **Ontología de polaridades**: 3 polaridades (Positivo, Negativo, Neutral).

- 4) Ontología educativa — COMPLETADO
  - Documentada en `docs/ONTOLOGY.md`: namespaces, ConceptSchemes, clases, propiedades y restricciones de anotación.
  - Ontología de aspectos y polaridades implementada y exportada en `data/exports/ontology_aspects.json`.
  - Función `load_ontology_from_json()` disponible para cargar la ontología en scripts ABSA.

- 5) Enriquecimiento de embeddings — EN PROGRESO
  - Ontología de aspectos disponible para construir grafo de conocimiento con NetworkX.
  - Generar representaciones semánticas (por aspecto/entidad) para el modelo ABSA usando Node2Vec.
  - Fusionar embeddings textuales (OpenAI) con embeddings de grafo (Node2Vec).

- 6) Modelo ABSA — PENDIENTE
  - Identificación de aspectos y polaridad por comentario.
  - Integración con grafo (anotaciones por nodo `Comment`).

- 7–9) Salidas ABSA y grafo enriquecido — PENDIENTE
  - Tripletas/SPO previstas: (Comment, hasTopic, Aspect), (Comment, hasPolarity, Polarity), vía `skos_annotations.csv`.

- 10) Validación — PENDIENTE
  - Métricas y validación humana; bucle de realimentación al grafo y al modelo.

- 11) Resultado modelo — PENDIENTE
  - Reportes y dashboards analíticos.

### Brechas y tareas clave
- (Opcional) Evaluar incorporación de `Author` y PROV en futuras iteraciones.
- ~~Definir ontología/TTL del esquema educativo~~ ✅ **COMPLETADO**: Ontología de aspectos educativos implementada.
- Implementar pipeline ABSA completo (detección de aspectos + polaridad usando LLM) y su exportación al grafo.
- Construir grafo NetworkX desde CSV de nodos/edges para Node2Vec.
- Diseñar validación y métricas (precisión, cobertura de aspectos, consistencia de relaciones).
