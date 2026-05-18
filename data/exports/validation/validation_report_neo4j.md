# Capítulo 5: Validación de Resultados (Neo4j)

**Fecha**: 2025-12-16 11:42

## 1. Resumen Ejecutivo
- **Muestra Evaluada**: 5 tripletas (Comentario-Aspecto-Sentimiento)
- **Precisión en Detección de Aspectos**: 100.00%
- **Relevancia Promedio del Aspecto (1-5)**: 4.00
- **Precisión en Clasificación de Sentimiento**: 80.00%

## 2. Análisis Detallado de Sentimientos
Métricas calculadas sobre los aspectos correctamente identificados.

| Clase | Versión LLM (Support) | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Neutral | 1.0 | 0.00 | 0.00 | 0.00 |
| Positivo | 4.0 | 0.80 | 1.00 | 0.89 |
| macro avg | 5.0 | 0.40 | 0.50 | 0.44 |
| weighted avg | 5.0 | 0.64 | 0.80 | 0.71 |

### Matriz de Confusión
Filas: Real (LLM), Columnas: Predicción (Sistema)

| | Positivo (Pred) | Negativo (Pred) | Neutral (Pred) |
|---|---|---|---|
|Positivo (Real)| 4 | 0 | 0 |
|Negativo (Real)| 0 | 0 | 0 |
|Neutral (Real)| 1 | 0 | 0 |

## 3. Análisis de Errores (Muestras)

| ID | Texto (Frag.) | Aspecto (Sys) | Sent (Sys) | Sent (Real) | Explicación |
|---|---|---|---|---|---|
| http://example.org/tic-absa/comment/59e3ace5ec4a89ecb6000a44 | las respuestas del foro 1 es q si se deb... | Foros | Positivo | Neutral | El aspecto 'Foros' es relevante ya que el comentario menciona 'las respuestas del foro 1'. Sin embargo, el sentimiento no es positivo ni negativo, sino más bien neutral, ya que el comentario simplemente describe una opinión expresada en el foro sin emitir un juicio de valor sobre el foro en sí. |