# Documentación del Sistema GraphRAG (TIC_ABSA_KG)

Este documento detalla la arquitectura, componentes y flujo de trabajo del sistema **GraphRAG (Graph Retrieval-Augmented Generation)** implementado para el proyecto de análisis de sentimientos educativo.

## 1. Arquitectura General

El sistema combina **Embeddings Vectoriales** (para similitud semántica) con un **Grafo de Conocimiento** (para contexto estructural y jerárquico) almacenado en Neo4j.

### 1.1. Fundamentos Teóricos: Embeddings y Node2Vec

El corazón del sistema reside en su capacidad para "entender" tanto el texto de los estudiantes como la estructura del conocimiento educativo. Esto se logra mediante una estrategia de **Embeddings Multimodales**:

#### A. Embeddings de Texto (OpenAI)
Utilizamos el modelo `text-embedding-3-small` de OpenAI para convertir el texto de cada comentario en un vector numérico.
*   **Qué captura**: La semántica del lenguaje natural (sinónimos, contexto, intención).
*   **Ejemplo**: Entiende que "el profe explica mal" es semánticamente cercano a "la didáctica del docente es deficiente".

#### B. Embeddings de Grafo (Node2Vec)
Aplicamos el algoritmo **Node2Vec** sobre la ontología de aspectos educativos (SKOS).
*   **Qué captura**: La topología y relaciones estructurales de los conceptos.
*   **Funcionamiento**: Node2Vec realiza "caminatas aleatorias" (random walks) sobre el grafo para aprender qué nodos "viven cerca" unos de otros.
*   **Beneficio**: El sistema aprende que el aspecto "Cuestionario" está estructuralmente relacionado con "Evaluación" y "Retos", incluso si el texto no los menciona explícitamente, permitiendo recuperar información contextualmente relevante.

#### C. Fusión Multimodal
Para cada comentario, generamos un **Vector Fusionado** que combina ambos mundos:
1.  Se normalizan ambos vectores.
2.  Se combinan para formar una representación única que se almacena en Neo4j.
3.  **Resultado**: Un vector que permite búsquedas que entienden tanto lo que el estudiante *dijo* como *de qué concepto educativo* está hablando.

---

## 2. Componentes Detallados

### 2.1. Semantic Pipeline Modificado
**Archivo**: `src/absa/semantic_pipeline.py`

Se actualizó el pipeline original para persistir los vectores fusionados.

*   **Entrada**: JSONs de comentarios (EVOLFUND, HG) + Ontología SKOS.
*   **Proceso**:
    *   Genera embeddings de texto y grafo.
    *   Fusiona los vectores.
    *   Realiza ABSA con GPT-4.
*   **Salida**: `data/processed/resultados_absa_completo.json` con el campo `vector_fusionado`.

### 2.2. Ingesta Jerárquica en Neo4j
**Archivo**: `src/rag/neo4j_ingest.py`

Script encargado de poblar la base de datos Neo4j reconstruyendo la jerarquía educativa.

*   **Esquema del Grafo**:
    *   **Jerarquía Educativa**:
        `(:BaseCourse) <-[:BELONGS_TO_BASE]- (:CourseEdition) <-[:BELONGS_TO_EDITION]- (:Thread) <-[:POSTED_IN]- (:Comment)`
    *   **Ontología de Aspectos**:
        `(:Aspect) -[:BROADER]-> (:Aspect)` (Jerarquía Padre-Hijo)
    *   **Análisis de Sentimientos**:
        `(:Comment) -[:MENTIONS {sentiment: '...', confidence: ...}]-> (:Aspect)`
*   **Índice Vectorial**: Crea un índice `comment_embedding` (128 dimensiones) en los nodos `Comment`.

### 2.3. Motor de Consulta (GraphRAG Engine)
**Archivo**: `src/rag/rag_engine.py`

Interfaz de consulta inteligente que permite:

1.  **Búsqueda Híbrida (Hybrid Search)**:
    *   Combina búsqueda vectorial (similitud) con navegación de grafo.
    *   Recupera el comentario, su aspecto, sentimiento y el curso al que pertenece.
2.  **Reportes Ejecutivos por Curso (`get_course_report`)**:
    *   Genera una "Ficha del Curso" automática.
    *   Calcula estadísticas de sentimiento y detecta los Top 5 "Puntos de Dolor" y "Fortalezas".
    *   Usa un LLM para redactar un resumen narrativo.
3.  **Filtrado Contextual**:
    *   Permite restringir las búsquedas a un curso específico mediante el parámetro `course_filter`.

### 2.4. Analytics de Grafo
**Archivo**: `src/rag/graph_analytics.py`

Script para realizar consultas puras de grafo (Cypher) que revelan patrones globales, como distribución de sentimientos por aspecto y detección de tendencias.

---

## 3. Validación y Verificación

### 3.1. Script de Validación
**Archivo**: `src/rag/validate_graph.py`
Verifica la integridad de la estructura del grafo (nodos, relaciones, ontología).

### 3.2. Pruebas Automatizadas
**Archivo**: `src/rag/test_extended.py`
Script que valida:
*   Generación correcta de reportes por curso.
*   Funcionamiento del filtrado de consultas.
*   Capacidad de respuesta a consultas globales.

---

## 4. Guía de Uso Rápida

### Ejecución Completa (Pipeline + Ingesta)
```powershell
./run_full_project.ps1
```

### Consultas Interactivas
```bash
python src/rag/rag_engine.py
# O consulta directa:
python src/rag/rag_engine.py "¿Qué opinan sobre los videos?"
```

### Generación de Reportes (Python)
```python
from src.rag.rag_engine import GraphRAGEngine
engine = GraphRAGEngine()

# Generar reporte ejecutivo
print(engine.get_course_report("course-v1:UTPL+HG+2016"))

# Consulta filtrada por curso
print(engine.query("problemas con tareas", course_filter="course-v1:UTPL+HG+2016"))
```
