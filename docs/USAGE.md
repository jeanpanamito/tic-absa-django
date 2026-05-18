# Guía de Uso — Pipeline End-to-End

## Requisitos
- Python 3.8+
- Instalar dependencias:
```bash
pip install -r requirements.txt
```

## 1) EDA y diagnóstico
```bash
python eda_analysis.py
# Revisa: data/exports/eda_report.txt
```

## 2) Limpieza y normalización
```bash
python src/preprocessing/cleaning_pipeline.py
# Salidas:
# - data/processed/cleaned_comments.csv
# - data/exports/cleaning_report.txt
```

## 3) Grafo SKOS
```bash
# Subconjunto de prueba
python -m src.graph_construction.skos_builder --limit 5000
# Completo
python -m src.graph_construction.skos_builder --limit 0
# Salidas:
# - data/exports/skos_nodes.csv
# - data/exports/skos_edges.csv
# - data/exports/skos_annotations.csv
# - data/exports/sample_skos.ttl
# - data/exports/ontology_aspects.json (ONTOLOGÍA DE ASPECTOS PARA ABSA)
```

### Uso de la Ontología de Aspectos

La ontología de aspectos puede ser cargada desde el JSON exportado:

```python
from src.graph_construction.skos_builder import load_ontology_from_json

# Cargar la ontología
ontology = load_ontology_from_json()

# Acceder a los componentes
aspects = ontology['ontologia_aspectos']
relations = ontology['relaciones_aspectos']
polarities = ontology['polaridades']
```

La ontología incluye:
- **8 aspectos educativos**: General, Contenido, Videos, Evaluacion, Retos, Tutoria, Plataforma, Foros
- **3 polaridades**: Positivo, Negativo, Neutral
- **Relaciones jerárquicas y semánticas** entre aspectos

## 4) ABSA (prototipo)
```bash
python -m src.absa.proto_aspects --limit 20000
# Salidas:
# - data/exports/aspect_spo.csv
# - data/exports/aspect_polarity.csv
# - data/exports/aspect_sample.ttl
```

## 5) Carga en triplestore (opcional)
- Usa GraphDB o Apache Jena Fuseki para cargar `sample_skos.ttl` y `aspect_sample.ttl`.
- Ejecuta consultas SPARQL, p. ej.: comentarios por curso, respuestas, aspectos detectados.

## 6) Consultas SPARQL locales (con `skos:note`)
```bash
python -m src.graph_construction.sparql_tests
```
Incluye ejemplos de:
- Comentarios por curso con `skos:note` (texto del comentario)
- Respuestas (replyTo) con nota del comentario origen y destino
- Anotaciones ABSA (topic/polarity) a partir de `skos_annotations.csv`

Comentario identificado: Las consultas confirman que cada comentario puede vincularse a su hilo y curso (edición/base) y su texto (`skos:note`), validando el modelo SKOS para trazabilidad.

## 6) Siguientes pasos
- Usar la ontología de aspectos (`ontology_aspects.json`) en el pipeline ABSA con embeddings (OpenAI) y Node2Vec.
- Construir grafo NetworkX desde los nodos/edges exportados para entrenar Node2Vec.
- Reemplazar el prototipo ABSA por un modelo entrenado con LLM (GPT-4o-mini).
- Exportar tripletas SPO completas y dashboards de análisis.
