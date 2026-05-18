# Capítulo 5: Validación de Resultados (Neo4j)

**Fecha**: 2025-12-16 15:03

## 1. Resumen Ejecutivo
- **Muestra Evaluada**: 700 tripletas (Comentario-Aspecto-Sentimiento)
- **Precisión en Detección de Aspectos**: 61.29%
- **Relevancia Promedio del Aspecto (1-5)**: 3.28
- **Precisión en Clasificación de Sentimiento**: 78.57%

## 2. Análisis por Curso

| Curso | Muestras | Prec. Aspecto (%) | Prec. Sentimiento (%) |
|---|---|---|---|
| course-v1:UTPL+HG13+2020_1 | 366 | 60.11 | 77.32 |
| course-v1:UTPL+HG-Ed6+2017_OCT | 46 | 67.39 | 73.91 |
| course-v1:UTPL+HG-Ed8+2018_1 | 29 | 58.62 | 86.21 |
| course-v1:UTPL+HG-Ed4+ABR_2017 | 26 | 53.85 | 80.77 |
| course-v1:UTPL+EVOLFUND5+2020_1 | 26 | 69.23 | 88.46 |
| course-v1:UTPL+HG11+2019_1 | 23 | 52.17 | 82.61 |
| course-v1:UTPL+HG10+2018_3 | 20 | 85.00 | 90.00 |
| course-v1:UTPL+HG14+2020_2 | 17 | 58.82 | 70.59 |
| course-v1:UTPL+HG15+2021_1 | 16 | 56.25 | 87.50 |
| course-v1:UTPL+HG20+2023_2 | 15 | 73.33 | 80.00 |
| course-v1:UTPL+EVOLFUND+2018_1 | 15 | 33.33 | 60.00 |
| course-v1:UTPL+HG-Ed3+2017-FEB | 13 | 46.15 | 100.00 |
| course-v1:UTPL+HG9+2018_2 | 13 | 84.62 | 84.62 |
| course-v1:UTPL+HG19+2023_1 | 12 | 91.67 | 75.00 |
| course-v1:UTPL+HG-Ed5+2017_JUN | 11 | 63.64 | 100.00 |
| course-v1:UTPL+EVOLFUND6+2020_2 | 7 | 57.14 | 71.43 |
| course-v1:UTPL+HG+2016 | 7 | 57.14 | 57.14 |
| course-v1:UTPL+EVOLFUND2+2018_2 | 6 | 66.67 | 33.33 |
| course-v1:UTPL+EVOLFUND7+2021_1 | 5 | 80.00 | 80.00 |
| course-v1:UTPL+EVOLFUND6+2021_2 | 5 | 40.00 | 100.00 |
| course-v1:UTPL+HG23+2025_1 | 4 | 100.00 | 100.00 |
| course-v1:UTPL+EVOLFUND7+2022_1 | 3 | 66.67 | 66.67 |
| course-v1:UTPL+EVOLFUND3+2018_3 | 3 | 66.67 | 66.67 |
| course-v1:UTPL+HG-Ed2+2017_ENE | 3 | 33.33 | 33.33 |
| course-v1:UTPL+HG16+2021_2 | 2 | 0.00 | 50.00 |
| course-v1:UTPL+HG17+2022_1 | 2 | 50.00 | 100.00 |
| course-v1:UTPL+HG21+2024_1 | 2 | 0.00 | 100.00 |
| course-v1:UTPL+HG12+2019_2 | 1 | 100.00 | 100.00 |
| course-v1:UTPL+HG-Ed7+2017_DIC | 1 | 0.00 | 0.00 |
| course-v1:UTPL+HG18+2022_2 | 1 | 100.00 | 100.00 |

## 3. Análisis Detallado de Sentimientos (Global)
Métricas calculadas sobre los aspectos correctamente identificados.

| Clase | Versión LLM (Support) | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Negativo | 124.0 | 0.94 | 0.89 | 0.91 |
| Neutral | 75.0 | 0.70 | 0.53 | 0.61 |
| Positivo | 230.0 | 0.86 | 0.96 | 0.91 |
| macro avg | 429.0 | 0.83 | 0.79 | 0.81 |
| weighted avg | 429.0 | 0.86 | 0.86 | 0.86 |

### Matriz de Confusión
Filas: Real (LLM), Columnas: Predicción (Sistema)

| | Positivo (Pred) | Negativo (Pred) | Neutral (Pred) |
|---|---|---|---|
|Positivo (Real)| 220 | 2 | 8 |
|Negativo (Real)| 5 | 110 | 9 |
|Neutral (Real)| 30 | 5 | 40 |

## 3. Análisis de Errores (Muestras)

| ID | Curso | Texto (Frag.) | Aspecto (Sys) | Sent (Sys) | Sent (Real) | Explicación |
|---|---|---|---|---|---|---|
| http://example.org/tic-absa/comment/5fa476eeec4a89e66d000793 | course-v1:UTPL+HG13+2020_1 | he aprendido bastante sobre co... | Actividades | Positivo | Positivo | El comentario se centra en el aprendizaje y los conocimientos adquiridos, no en las 'Actividades'. El sentimiento positivo es correcto, ya que el estudiante expresa satisfacción con lo aprendido. |
| http://example.org/tic-absa/comment/5ea1fbfeec4a89a684000744 | course-v1:UTPL+HG13+2020_1 | me encuentro con altas expecta... | Contenido | Positivo | Positivo | El comentario expresa un sentimiento positivo, ya que 'altas expectativas' generalmente implica una anticipación favorable. Sin embargo, el aspecto 'Contenido' no es explícito ni implícito en el comentario. El estudiante no menciona específicamente el contenido del curso, sino una expectativa general hacia el curso. |
| http://example.org/tic-absa/comment/5fa2ef01ec4a8981a1000701 | course-v1:UTPL+EVOLFUND6+2020_2 | Al parecer nadie responderá Ya... | Tutoria | Negativo | Negativo | El comentario expresa frustración por la falta de respuesta o acción, lo cual es negativo. Sin embargo, el aspecto 'Tutoria' no es explícito ni implícito en el comentario. El aspecto correcto podría ser 'atención al estudiante' o 'soporte'. |
| http://example.org/tic-absa/comment/5e9e67f0ec4a89a9a8000057 | course-v1:UTPL+HG13+2020_1 | Opino que nos iría mucho mejor... | General | Positivo | Neutral | El aspecto 'General' es demasiado vago y no refleja el tema específico del comentario, que es la enseñanza de ciertos conocimientos desde la escuela o el colegio. El sentimiento detectado como 'Positivo' no es correcto, ya que el comentario expresa una opinión sobre una mejora potencial, lo cual es más neutral que positivo. |
| http://example.org/tic-absa/comment/5e96a16eec4a897eb10005f8 | course-v1:UTPL+HG13+2020_1 | pienso que la agricultura es i... | Actividades | Positivo | Positivo | El aspecto 'Actividades' es demasiado general y no se corresponde directamente con 'agricultura', que es el tema central del comentario. El sentimiento positivo es correcto, ya que el comentario resalta la importancia de la agricultura de manera positiva. |
| http://example.org/tic-absa/comment/5fd3e1e2ec4a89e66d0012fe | course-v1:UTPL+HG14+2020_2 | PROBLEMAS DE INTERNET EN MI LO... | Evaluacion | Positivo | Negativo | El comentario se refiere a problemas de conectividad a internet, no a la 'Evaluación'. Además, el sentimiento es claramente negativo, ya que el estudiante expresa una dificultad que le impidió completar una tarea. |
| http://example.org/tic-absa/comment/5f8e4594ec4a89a6840056a9 | course-v1:UTPL+HG14+2020_2 | un gusto compartir con uds est... | Tutoria | Positivo | Positivo | El comentario expresa un sentimiento positivo sobre la experiencia de aprendizaje, pero no menciona específicamente 'tutoria'. El aspecto 'tutoria' no es relevante ni explícito en el comentario. El sentimiento positivo es correcto, ya que el estudiante muestra satisfacción con la experiencia de aprendizaje. |
| http://example.org/tic-absa/comment/5ebc714dec4a89a684002ab8 | course-v1:UTPL+HG13+2020_1 | ayer estaba realizando el Test... | Evaluacion | Neutral | Negativo | El aspecto 'Evaluacion' es razonable ya que el comentario menciona un 'Test', que es una forma de evaluación. Sin embargo, el sentimiento es negativo porque el estudiante menciona problemas con el internet que afectaron el envío del test, lo cual es una experiencia frustrante. |
| http://example.org/tic-absa/comment/5b076b6aec4a89c2cf000446 | course-v1:UTPL+EVOLFUND+2018_1 | sigo sin poder calificar a mis... | General | Negativo | Negativo | El aspecto 'General' es demasiado vago y no captura el problema específico mencionado en el comentario, que es la dificultad para calificar a los compañeros. El sentimiento negativo es correcto, ya que el comentario expresa frustración o insatisfacción. |
| http://example.org/tic-absa/comment/5cbdbf75ec4a89109f00055f | course-v1:UTPL+HG11+2019_1 | este curso no ayude a todos lo... | General | Positivo | Negativo | El aspecto 'General' es demasiado vago y no refleja el tema específico del comentario, que es la efectividad del curso en enseñar sobre agricultura. El sentimiento detectado como 'Positivo' es incorrecto, ya que el comentario expresa una crítica negativa sobre la capacidad del curso para ayudar a los estudiantes a comprender la agricultura. |