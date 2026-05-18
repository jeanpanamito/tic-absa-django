# Consultas SPARQL para Explorar el Grafo Enriquecido con ABSA

Este documento contiene consultas SPARQL de ejemplo para explorar el grafo SKOS enriquecido con resultados ABSA en GraphDB.

## Prefijos Comunes

Todas las consultas usan estos prefijos:

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
PREFIX schema: <http://schema.org/>
PREFIX prov: <http://www.w3.org/ns/prov#>
BASE <http://example.org/tic-absa/>
```

---

## Consulta 1: Comentarios con Anotaciones ABSA (Detalle Completo)

Muestra comentarios con todas sus anotaciones ABSA, incluyendo aspectos, polaridades y metadatos.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?comment ?commentText ?aspect ?polarity ?confidence ?mention ?justification
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?annotation absa:confidence ?confidence .
    ?annotation absa:mention ?mention .
    ?annotation absa:justification ?justification .
    ?comment skos:note ?commentText .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
ORDER BY DESC(?confidence)
LIMIT 20
```

**Resultado esperado:** Lista de comentarios con sus anotaciones ABSA ordenadas por confianza descendente.

---

## Consulta 2: Jerarquía Completa: CourseBase → CourseEdition → Thread → Comment

Muestra la jerarquía completa del grafo desde el curso base hasta los comentarios, incluyendo las anotaciones ABSA.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?baseCourse ?courseEdition ?thread ?comment ?aspect ?polarity
WHERE {
    # Jerarquía: CourseBase -> CourseEdition -> Thread -> Comment
    ?courseEdition skos:broader ?baseCourse .
    ?thread skos:broader ?courseEdition .
    ?comment skos:broader ?thread .
    
    # Anotaciones ABSA del comentario
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    
    # Labels para legibilidad
    ?baseCourse skos:prefLabel ?baseLabel .
    ?courseEdition skos:prefLabel ?courseLabel .
    ?thread skos:prefLabel ?threadLabel .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
ORDER BY ?baseCourse ?courseEdition ?thread ?comment
LIMIT 30
```

**Resultado esperado:** Vista jerárquica completa mostrando cómo se conectan los cursos, hilos y comentarios con sus anotaciones.

---

## Consulta 3: Comentarios con Sentimientos Positivos (Alta Confianza)

Encuentra comentarios con sentimientos positivos y alta confianza, mostrando los aspectos mencionados.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?comment ?commentText ?aspect ?mention ?confidence ?similarity
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasPolarity <polarity/Positivo> .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:confidence ?confidence .
    ?annotation absa:similarity ?similarity .
    ?annotation absa:mention ?mention .
    ?comment skos:note ?commentText .
    ?aspect skos:prefLabel ?aspectLabel .
    
    # Filtrar por alta confianza
    FILTER(?confidence >= 0.8)
}
ORDER BY DESC(?confidence) DESC(?similarity)
LIMIT 25
```

**Resultado esperado:** Comentarios positivos con confianza alta, ordenados por confianza y similitud.

---

## Consulta 4: Comentarios con Sentimientos Negativos por Aspecto

Agrupa comentarios negativos por aspecto, mostrando conteos y ejemplos.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?aspect ?aspectLabel 
       (COUNT(?annotation) AS ?totalNegativos)
       (AVG(?confidence) AS ?confianzaPromedio)
       (SAMPLE(?mention) AS ?ejemploMencion)
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasPolarity <polarity/Negativo> .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:confidence ?confidence .
    ?annotation absa:mention ?mention .
    ?aspect skos:prefLabel ?aspectLabel .
}
GROUP BY ?aspect ?aspectLabel
ORDER BY DESC(?totalNegativos)
```

**Resultado esperado:** Estadísticas de comentarios negativos agrupados por aspecto, con conteo total y confianza promedio.

---

## Consulta 5: Distribución de Sentimientos por Aspecto (Resumen Estadístico)

Muestra un resumen completo de la distribución de sentimientos (Positivo, Negativo, Neutral) para cada aspecto.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?aspect ?aspectLabel ?polarity ?polarityLabel
       (COUNT(?annotation) AS ?cantidad)
       (AVG(?confidence) AS ?confianzaPromedio)
       (MIN(?confidence) AS ?confianzaMinima)
       (MAX(?confidence) AS ?confianzaMaxima)
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?annotation absa:confidence ?confidence .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
GROUP BY ?aspect ?aspectLabel ?polarity ?polarityLabel
ORDER BY ?aspectLabel ?polarityLabel
```

**Resultado esperado:** Tabla completa con distribución de sentimientos por aspecto, incluyendo estadísticas de confianza.

---

## Consultas Adicionales Útiles

### Consulta 6: Comentarios con Múltiples Aspectos

Encuentra comentarios que tienen múltiples aspectos detectados (más de una anotación).

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?comment ?commentText 
       (COUNT(?annotation) AS ?numAspectos)
       (GROUP_CONCAT(DISTINCT ?aspectLabel; SEPARATOR=", ") AS ?aspectos)
       (GROUP_CONCAT(DISTINCT ?polarityLabel; SEPARATOR=", ") AS ?polaridades)
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?comment skos:note ?commentText .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
GROUP BY ?comment ?commentText
HAVING (COUNT(?annotation) > 1)
ORDER BY DESC(?numAspectos)
LIMIT 20
```

### Consulta 7: Aspectos más Problemáticos (Mayor % Negativo)

Identifica qué aspectos tienen mayor porcentaje de comentarios negativos.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?aspect ?aspectLabel
       (COUNT(?annotation) AS ?total)
       (SUM(IF(?polarity = <polarity/Negativo>, 1, 0)) AS ?negativos)
       ((SUM(IF(?polarity = <polarity/Negativo>, 1, 0)) * 100.0 / COUNT(?annotation)) AS ?porcentajeNegativo)
WHERE {
    ?comment absa:hasAnnotation ?annotation .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    ?aspect skos:prefLabel ?aspectLabel .
}
GROUP BY ?aspect ?aspectLabel
HAVING (COUNT(?annotation) >= 10)
ORDER BY DESC(?porcentajeNegativo)
```

### Consulta 8: Análisis por Curso y Aspecto

Combina información de cursos con análisis de aspectos y sentimientos.

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX absa: <http://example.org/tic-absa/absa#>
BASE <http://example.org/tic-absa/>

SELECT ?baseCourse ?courseEdition ?aspect ?polarity
       (COUNT(?annotation) AS ?cantidad)
WHERE {
    ?annotation absa:inBaseCourse ?baseCourse .
    ?annotation absa:inCourse ?courseEdition .
    ?annotation absa:hasAspect ?aspect .
    ?annotation absa:hasPolarity ?polarity .
    
    ?baseCourse skos:prefLabel ?baseLabel .
    ?courseEdition skos:prefLabel ?courseLabel .
    ?aspect skos:prefLabel ?aspectLabel .
    ?polarity skos:prefLabel ?polarityLabel .
}
GROUP BY ?baseCourse ?courseEdition ?aspect ?polarity
ORDER BY ?baseCourse ?courseEdition ?aspect ?polarity
```

---

## Notas de Uso

1. **Límites**: Todas las consultas incluyen `LIMIT` para evitar resultados muy grandes. Ajusta según necesites.

2. **Filtros**: Puedes agregar filtros adicionales como:
   - `FILTER(?confidence >= 0.7)` para filtrar por confianza mínima
   - `FILTER(CONTAINS(?commentText, "palabra"))` para buscar texto específico
   - `FILTER(?aspect = <aspect/Evaluacion>)` para un aspecto específico

3. **Ordenamiento**: Cambia `ORDER BY` según necesites:
   - `ORDER BY DESC(?confidence)` - Por confianza descendente
   - `ORDER BY ?aspectLabel` - Por nombre de aspecto
   - `ORDER BY DESC(?cantidad)` - Por cantidad descendente

4. **Agregaciones**: Las funciones de agregación disponibles incluyen:
   - `COUNT()` - Contar
   - `AVG()` - Promedio
   - `SUM()` - Suma
   - `MIN()` / `MAX()` - Mínimo/Máximo
   - `GROUP_CONCAT()` - Concatenar valores (útil para listas)

5. **Compatibilidad GraphDB**: Todas las consultas son compatibles con GraphDB y usan sintaxis SPARQL 1.1 estándar.

