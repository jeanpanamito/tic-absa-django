# Enriquecimiento del Grafo SKOS con Resultados ABSA

Este documento describe cómo enriquecer el grafo SKOS generado por `skos_builder.py` con los resultados del pipeline ABSA (`semantic_pipeline.py`) para cargar en GraphDB.

## Archivos Generados

### 1. Ontología ABSA (`absa_ontology.ttl`)
Define las clases y propiedades del namespace ABSA:
- **Clase**: `absa:Annotation` - Representa una anotación ABSA
- **Propiedades de objeto**:
  - `absa:hasAnnotation` - Comment → Annotation
  - `absa:hasAspect` - Annotation → Aspect
  - `absa:hasPolarity` - Annotation → Polarity
  - `absa:inCourse` - Annotation → CourseEdition
  - `absa:inBaseCourse` - Annotation → CourseBase
  - `absa:inThread` - Annotation → Thread
- **Propiedades de datos**:
  - `absa:confidence` - Confianza de la anotación (float)
  - `absa:similarity` - Similitud semántica (float)
  - `absa:mention` - Texto mencionado (string)
  - `absa:justification` - Justificación (string)
  - `absa:embeddingDimension` - Dimensión del embedding (integer)

### 2. Tripletas de Enriquecimiento (`absa_enrichment.ttl`)
Contiene todas las tripletas que conectan comentarios con aspectos y polaridades detectados por el pipeline ABSA.

## Uso

### Generar las Tripletas TTL

```bash
# Generar tripletas desde resultados ABSA completos
python -m src.graph_construction.absa_enrichment

# Especificar archivos de entrada y salida
python -m src.graph_construction.absa_enrichment \
    --input data/exports/resultados_absa_completo.json \
    --output data/exports/absa_enrichment.ttl

# Modo prueba (solo primeros 100 resultados)
python -m src.graph_construction.absa_enrichment --limit 100
```

### Cargar en GraphDB

1. **Cargar la ontología base SKOS** (si no está ya cargada):
   ```bash
   # Primero generar el grafo SKOS base
   python -m src.graph_construction.skos_builder
   ```
   Esto genera `data/exports/sample_skos.ttl`

2. **Cargar la ontología ABSA**:
   - En GraphDB, importa `src/graph_construction/absa_ontology.ttl`
   - Esto define las clases y propiedades del namespace ABSA

3. **Cargar las tripletas de enriquecimiento**:
   - En GraphDB, importa `data/exports/absa_enrichment.ttl`
   - Esto conecta los comentarios existentes con aspectos y polaridades

## Estructura de Relaciones

```
Comment (skos:Concept)
  └─> absa:hasAnnotation
      └─> Annotation (absa:Annotation)
          ├─> absa:hasAspect → Aspect (skos:Concept)
          ├─> absa:hasPolarity → Polarity (skos:Concept)
          ├─> absa:inCourse → CourseEdition (skos:Concept) [opcional]
          ├─> absa:inBaseCourse → CourseBase (skos:Concept) [opcional]
          ├─> absa:inThread → Thread (skos:Concept) [opcional]
          ├─> absa:confidence (xsd:float)
          ├─> absa:similarity (xsd:float)
          ├─> absa:mention (xsd:string)
          ├─> absa:justification (xsd:string)
          └─> absa:embeddingDimension (xsd:integer)
```

## Consultas SPARQL de Ejemplo

### Obtener todas las anotaciones ABSA de un comentario

```sparql
PREFIX absa: <http://example.org/tic-absa/absa#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
BASE <http://example.org/tic-absa/>

SELECT ?comment ?annotation ?aspect ?polarity ?confidence ?mention
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?annotation absa:confidence ?confidence .
    ?annotation absa:mention ?mention .
    ?comment skos:prefLabel ?commentLabel .
    FILTER(CONTAINS(STR(?comment), "583ef5a3ec4a89449800065f"))
}
ORDER BY DESC(?confidence)
```

### Contar anotaciones por aspecto y polaridad

```sparql
PREFIX absa: <http://example.org/tic-absa/absa#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
BASE <http://example.org/tic-absa/>

SELECT ?aspect ?polarity (COUNT(?annotation) AS ?count)
WHERE {
    ?annotation a absa:Annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
GROUP BY ?aspect ?polarity
ORDER BY DESC(?count)
```

### Encontrar comentarios con sentimientos negativos sobre un aspecto específico

```sparql
PREFIX absa: <http://example.org/tic-absa/absa#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
BASE <http://example.org/tic-absa/>

SELECT ?comment ?commentText ?mention ?justification ?confidence
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect <aspect/Evaluacion> .
    ?annotation absa:hasPolarity <polarity/Negativo> .
    ?annotation absa:mention ?mention .
    ?annotation absa:justification ?justification .
    ?annotation absa:confidence ?confidence .
    ?comment skos:note ?commentText .
    FILTER(?confidence > 0.8)
}
ORDER BY DESC(?confidence)
LIMIT 20
```

### Análisis de sentimientos por curso

```sparql
PREFIX absa: <http://example.org/tic-absa/absa#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
BASE <http://example.org/tic-absa/>

SELECT ?course ?aspect ?polarity (COUNT(?annotation) AS ?count)
WHERE {
    ?annotation a absa:Annotation .
    ?annotation absa:inCourse ?course .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?course skos:prefLabel ?courseLabel .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
GROUP BY ?course ?aspect ?polarity
ORDER BY ?course ?aspect ?polarity
```

## Orden de Carga en GraphDB

Para asegurar que todas las referencias estén disponibles, carga los archivos en este orden:

1. **Ontología base SKOS** (`data/exports/sample_skos.ttl`)
   - Contiene todos los ConceptSchemes, Concepts y relaciones básicas
   - Incluye: CourseBase, CourseEdition, Thread, Comment, Aspect, Polarity

2. **Ontología ABSA** (`src/graph_construction/absa_ontology.ttl`)
   - Define las clases y propiedades del namespace ABSA
   - Debe cargarse antes de las tripletas de enriquecimiento

3. **Tripletas de enriquecimiento** (`data/exports/absa_enrichment.ttl`)
   - Conecta los comentarios existentes con aspectos y polaridades
   - Requiere que los comentarios, aspectos y polaridades ya existan en el grafo

## Estadísticas

Después de generar las tripletas, el script muestra:
- Total de anotaciones ABSA generadas
- Número de comentarios únicos con anotaciones
- Aspectos detectados
- Polaridades detectadas
- Conteo de relaciones generadas

## Notas

- Los IDs de anotación se generan como: `annotation/{comment_id}_{aspecto}_{sentimiento}_{idx}`
- Todas las referencias a comentarios, aspectos y polaridades usan los IRIs generados por `skos_builder.py`
- Los metadatos opcionales (course_id, base_course, thread_id) solo se incluyen si están presentes en los resultados ABSA
- Las tripletas son compatibles con GraphDB y otros motores RDF estándar

