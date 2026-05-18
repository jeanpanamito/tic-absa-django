## Roadmap — ABSA + Grafo de Conocimiento (Tesis)

### Objetivo General
Desarrollar un modelo ABSA y un grafo de conocimiento para identificar aspectos clave en comentarios estudiantiles y representar sus relaciones.

### Entregables y Cronograma (Prácticum 4.1 y 4.2)

1) Revisión de literatura y recopilación de datos (1 mes) — 4.1
- Entregables: matriz bibliográfica, criterios de ABSA educativos, fuentes de datos.
- Métrica: ≥30 referencias clave; dataset base consolidado.

2) Preprocesamiento y preparación de datos (1 mes)
- Hecho: pipeline de limpieza (`cleaning_pipeline.py`), validación y reporte.
- Próximo: particionado de datos para ABSA y muestreos estratificados.
- Métrica: 100% datos con texto limpio; 0 duplicados.

3) Detección de relaciones y construcción del grafo (1.5 meses)
- Hecho: exportación SKOS con jerarquía (CourseBase, CourseEdition, Thread, Comment) y `replyTo` (`skos:related`).
- Próximo: poblar esquemas `aspect` y `polarity` desde ABSA y anotar comentarios.
- Métrica: cobertura de relaciones >90% y consistencia jerárquica.

4) Implementación del modelo ABSA (1.5 meses) — 4.2
- Próximo: baseline léxico; luego modelo supervisado/transformers.
- Salidas: `aspect_terms`, `aspect_polarity` por comentario.
- Métrica: F1 aspecto ≥0.70 (piloto) y polaridad ≥0.75.

5) Evaluación y validación del prototipo (1 mes)
- Diseño de conjunto de validación manual y métricas (precisión, cobertura, coherencia grafo).
- Métrica: acuerdo inter-anotador ≥0.75; mejoras iterativas registradas.

6) Documentación (1 mes)
- Manual técnico y memoria de tesis con anexos (TTL, CSVs, scripts).

### Backlog inmediato (siguiente sprint)
- [ ] Definir y poblar `scheme/aspect` y `scheme/polarity` a partir de ABSA.
- [ ] Completar `docs/ONTOLOGY.md` con catálogo de aspectos/polaridades finales.
- [ ] Prototipo ABSA: detección de aspectos + polaridad, y volcado a `skos_annotations.csv`.
- [ ] Exportar TTL de anotaciones y ejemplos de consultas SPARQL.

### Riesgos y mitigaciones
- Fechas incompletas → imputación y marca de procedencia.
- Desequilibrio de clases en ABSA → muestreo y pérdida focal.
- Ruido en comentarios → reglas de limpieza estrictas y QA manual.
