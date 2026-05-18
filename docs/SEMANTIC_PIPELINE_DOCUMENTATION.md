# Documentación Detallada: Semantic Pipeline
**Archivo**: `src/absa/semantic_pipeline.py`

Este documento explica paso a paso el funcionamiento del script `semantic_pipeline.py`, el componente central del sistema que transforma los comentarios crudos en datos enriquecidos listos para el Grafo de Conocimiento.

## 1. Propósito General
El script orquesta un flujo de trabajo complejo que:
1.  Carga comentarios educativos (datasets HG y EVOLFUND).
2.  Carga la ontología de aspectos (SKOS).
3.  Genera representaciones vectoriales (Embeddings) tanto del texto como de la estructura del conocimiento.
4.  Utiliza GPT-4 para realizar un Análisis de Sentimientos Basado en Aspectos (ABSA) guiado por la ontología.
5.  Fusiona la información y la persiste para su ingesta en Neo4j.

---

## 2. Flujo de Ejecución Paso a Paso

### Paso 1: Configuración e Importaciones
El script comienza importando librerías clave:
*   `openai`: Para generación de embeddings de texto y llamadas a GPT-4.
*   `networkx`: Para construir y manipular el grafo de la ontología en memoria.
*   `node2vec`: Para generar embeddings estructurales a partir del grafo.
*   `pandas`: Para manipulación eficiente de datos tabulares (comentarios).

### Paso 2: Carga de Datos (`cargar_comentarios`)
*   Lee los archivos JSON crudos (`INPUT_HG_JSON`, `INPUT_EVOLFUND_JSON`).
*   Aplica filtros de limpieza:
    *   Elimina comentarios vacíos o muy cortos (< 20 caracteres).
    *   Elimina duplicados por ID.
    *   Filtra por curso base si se especifica el argumento `--base-course`.
    *   Limita la cantidad de registros si se usa `--limit`.

### Paso 3: Carga de Ontología (`cargar_ontologia`)
*   Utiliza `skos_builder` para cargar la estructura jerárquica de aspectos educativos.
*   Obtiene:
    *   **Aspectos**: Nodos con descripciones (ej. "Evaluación", "Videos").
    *   **Relaciones**: Tripletas (Sujeto, Predicado, Objeto) que definen la jerarquía (`BROADER`) y relaciones semánticas (`RELATED`).

### Paso 4: Construcción del Grafo y Node2Vec (`Fase E`)
Esta es una fase crítica para dotar al sistema de "conciencia estructural".
1.  **Construcción del Grafo (`construir_grafo_conocimiento`)**:
    *   Crea un grafo dirigido (`nx.DiGraph`) usando NetworkX.
    *   Añade cada aspecto como un nodo.
    *   Añade aristas para relaciones jerárquicas (Padre -> Hijo) y semánticas.
2.  **Entrenamiento Node2Vec (`entrenar_node2vec`)**:
    *   Ejecuta el algoritmo Node2Vec sobre el grafo construido.
    *   Realiza "caminatas aleatorias" (random walks) para aprender la topología.
    *   **Resultado**: Un vector de 128 dimensiones para cada aspecto, donde aspectos estructuralmente cercanos tienen vectores similares.

### Paso 5: Precomputación de Embeddings de Aspectos (`Fase D-PRE`)
*   Para cada aspecto de la ontología, genera un embedding de texto usando OpenAI (`text-embedding-3-small`).
*   Usa el formato: `"Aspecto: {nombre}. Descripción: {descripcion}"`.
*   Esto sirve como referencia semántica para comparar con el texto de los comentarios.

### Paso 6: Procesamiento de Comentarios (Bucle Principal)
Itera sobre cada comentario pendiente y realiza lo siguiente:

#### A. Embedding del Comentario (`Fase D`)
*   Envía el texto del comentario a la API de OpenAI.
*   Obtiene un vector denso (embedding) que representa el significado del comentario.

#### B. Cálculo de Similitud Semántica (`Fase F`)
*   Calcula la similitud coseno entre el embedding del comentario y los embeddings de todos los aspectos (precomputados en el Paso 5).
*   Identifica los **Top 3 aspectos** más relevantes semánticamente. Esto ayuda a guiar al LLM (aunque el LLM tiene la decisión final).

#### C. Análisis con GPT-4 (`Fase G`)
*   Construye un prompt detallado que incluye:
    *   La ontología completa (jerarquizada).
    *   El comentario del estudiante.
    *   Pistas sobre los aspectos más relevantes (basado en la similitud calculada).
*   Solicita a GPT-4 (`gpt-4o-mini`) que extraiga:
    *   Aspectos mencionados (de la lista oficial).
    *   Sentimiento (Positivo, Negativo, Neutral).
    *   Justificación (cita textual).
    *   Confianza del análisis.
*   Fuerza una salida en formato JSON estricto.

#### D. Fusión Multimodal y Persistencia (`Fase H`)
*   Para cada aspecto detectado por GPT-4:
    1.  Recupera el embedding de texto del comentario.
    2.  Recupera el embedding de grafo (Node2Vec) del aspecto mencionado.
    3.  **Fusión**: Combina ambos vectores (concatenación o promedio ponderado) para crear el `vector_fusionado`.
    4.  Crea un objeto `ResultadoABSA` con todos los metadatos y el vector fusionado.
*   Guarda resultados parciales y checkpoints para evitar pérdida de datos en procesos largos.

### Paso 7: Finalización
*   Calcula y muestra los costos estimados de la ejecución (tokens de OpenAI).
*   Genera el archivo final JSON (`resultados_absa_completo.json`) listo para ser ingerido por Neo4j.

---

## 3. Argumentos de Línea de Comandos
El script soporta varios argumentos para controlar su ejecución:
*   `--limit N`: Procesa solo los primeros N comentarios.
*   `--base-course ID`: Filtra comentarios de un curso específico (ej. "EVOLFUND").
*   `--resume`: Continúa desde el último checkpoint guardado.
*   `--checkpoint-file PATH`: Define la ruta del archivo de checkpoint.
*   `--gpt-model MODEL`: Especifica el modelo de GPT a usar (default: `gpt-4o-mini`).

## 4. Salida
El archivo resultante contiene una lista de objetos con la siguiente estructura:
```json
{
  "id_comentario": "...",
  "aspecto": "Evaluación",
  "sentimiento": "Negativo",
  "mencion": "el examen fue muy difícil",
  "justificacion": "...",
  "vector_fusionado": [0.12, -0.45, ...], // Vector híbrido Texto+Grafo
  "course_id": "...",
  ...
}
```
Este JSON es la entrada directa para el script de ingesta `neo4j_ingest.py`.
