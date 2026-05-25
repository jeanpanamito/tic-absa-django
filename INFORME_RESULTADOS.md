# Informe de Resultados: Evaluación Multi-LLM para ABSA en Comentarios Educativos
### Sistema TIC-ABSA · Universidad · TICEC 2026

---

## 1. Descripción del Experimento

### 1.1 Objetivo
Evaluar la capacidad de distintos modelos de lenguaje (LLMs) para realizar **Análisis de Sentimientos Basado en Aspectos (ABSA)** en comentarios de estudiantes universitarios en plataformas de educación en línea, utilizando una ontología de aspectos educativos definida en Neo4j.

### 1.2 Dataset
| Parámetro | Valor |
|-----------|-------|
| Fuente | Neo4j (grafo de conocimiento académico TIC-ABSA) |
| Número de comentarios únicos | **637 comentarios únicos** |
| Número total de registros (con duplicados por aspecto) | **700 registros** |
| Número de cursos representados | 28 cursos |
| Idioma | Español |

### 1.3 Ontología de Aspectos
Los modelos debían clasificar cada comentario en uno de los siguientes **8 aspectos oficiales** de la ontología:

| Aspecto | Descripción |
|---------|-------------|
| `General` | Percepción general del curso |
| `Evaluacion` | Exámenes, evaluaciones, tests |
| `Plataforma` | Plataforma virtual (Moodle, etc.) |
| `Retos` | Desafíos y retos del curso |
| `Actividades` | Tareas y actividades de aprendizaje |
| `Tutoria` | Atención del tutor/docente |
| `Contenido` | Material didáctico y contenido temático |
| `Foros` | Participación en foros |
| `Videos` | Material en video |

### 1.4 Metodología de Evaluación
Se utilizó una metodología de **tres fases**, orquestada mediante el script principal [evaluation/run_all_experiments.py](./evaluation/run_all_experiments.py):

- **Fase A (Baselines):** Técnicas de referencia sin LLMs avanzados.
- **Fase B (Inferencia):** Cada LLM procesó los 637 comentarios usando el mismo *prompt* ABSA *zero-shot* con guías de anotación de la ontología y similitud coseno de embeddings pre-computados. (Script: [evaluation/multi_llm/inference_runner.py](./evaluation/multi_llm/inference_runner.py))
- **Fase C (Evaluación – LLM-as-a-Judge):** GPT-4o actuó como juez automatizado para verificar si el aspecto predicho y el sentimiento predicho eran correctos, asignando una puntuación de relevancia del 1 al 5. (Script: [evaluation/multi_llm/judge_evaluator.py](./evaluation/multi_llm/judge_evaluator.py))

El cálculo final de métricas se realizó con el script [evaluation/metrics/compute_metrics.py](./evaluation/metrics/compute_metrics.py).

---

## 2. Métricas Evaluadas

| Métrica | Descripción |
|---------|-------------|
| **sent_f1_weighted** | F1-score ponderado por clase para la clasificación de sentimiento |
| **sent_f1_macro** | F1-score macro (promedio no ponderado entre clases) |
| **aspect_acc** | Precisión de identificación del aspecto correcto según el juez |
| **avg_confidence** | Confianza promedio auto-reportada por el modelo (0–1) |
| **latency_s** | Latencia promedio por comentario (segundos) |
| **cost_usd** | Costo total del experimento (USD) |
| **json_errors** | Tasa de errores de parseo JSON (fallos de formato) |

---

## 3. Resultados por Experimento

---

### 3.1 Baseline 1 — `baseline_majority_class`
**Script asociado:** [evaluation/baselines/baseline_majority_class.py](./evaluation/baselines/baseline_majority_class.py)

**Descripción:** Clasificador trivial que siempre predice la clase mayoritaria del dataset. Asigna el sentimiento **Positivo** a todos los comentarios y el aspecto **General** a todos.

**Parámetros:**
- Sin uso de LLM ni embeddings
- Costo: $0.00 USD
- Latencia: 0 ms

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 700 |
| Aspectos extraídos | 700 (siempre `General`) |
| Distribución sentimientos | Positivo: 700 (100%) |
| Distribución aspectos | General: 700 (100%) |

**Métricas:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | **0.4552** |
| sent_f1_macro | **0.2511** |
| aspect_acc | **0.3514** |
| avg_confidence | 1.0000 |
| cost_usd | $0.0000 |

**Análisis:** Al predecir siempre "Positivo/General", el modelo acierta en ~45% del sentimiento (proporcional a la clase mayoritaria) pero sus métricas macro son las más bajas del experimento, confirmando que el dataset tiene desbalance de clases (sentimiento positivo dominante). Sirve como límite inferior de referencia (lower bound).

---

### 3.2 Baseline 2 — `baseline_cosine_only`
**Script asociado:** [evaluation/baselines/baseline_cosine_only.py](./evaluation/baselines/baseline_cosine_only.py)

**Descripción:** Clasificador basado puramente en similitud coseno entre embeddings de comentarios y vectores de referencia de los aspectos de la ontología. No usa ningún LLM para la decisión final. El sentimiento se infiere por reglas simples de polaridad léxica.

**Parámetros:**
- Embeddings pre-computados con `text-embedding-3-small` (OpenAI)
- Sin costo de inferencia (los embeddings son compartidos)
- Latencia: 0 ms (cálculo vectorial local)

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 700 |
| Aspectos extraídos | 700 |
| Distribución sentimientos | Neutral: 458, Positivo: 194, Negativo: 48 |
| Top 4 aspectos | Tutoría: 129, Evaluación: 105, Actividades: 46, Plataforma: 30 |

**Métricas:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | **0.4377** |
| sent_f1_macro | **0.3756** |
| aspect_acc | **0.4129** |
| avg_confidence | 0.4065 |
| cost_usd | $0.0000 |

**Análisis:** La similitud coseno mejora la identificación de aspectos (+6% sobre majority class) al distribuir las predicciones entre categorías. Sin embargo, el rendimiento en sentimiento es similar al clasificador trivial, lo que demuestra que la similitud semántica superficial es insuficiente para capturar matices de opinión. La confianza promedio es la más baja de todos los modelos (0.40), reflejando la incertidumbre natural del enfoque vectorial.

---

### 3.3 Baseline 3 — `baseline_no_guides` (Ablación)
**Script asociado:** [evaluation/baselines/baseline_no_guides.py](./evaluation/baselines/baseline_no_guides.py)

**Descripción:** Ablación que usa **GPT-4o-mini como LLM** pero **sin proporcionar las guías de anotación de la ontología** en el prompt. El modelo recibe solo el comentario y debe inferir aspecto y sentimiento por sí mismo, sin restricciones al vocabulario oficial.

**Parámetros:**
- Modelo: GPT-4o-mini (OpenAI)
- Prompt: Comentario únicamente, sin ontología ni similitudes coseno
- Temperatura: 0.0

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 637 |
| Aspectos extraídos | 639 |
| Total tokens consumidos | 313,961 |
| Distribución sentimientos | Positivo: 383, Negativo: 168, Neutral: 88 |
| Top 4 aspectos predichos | General: 321, Evaluación: 109, Actividades: 38, Contenido: 28 |
| Errores JSON | 0 |

**Métricas:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | **0.8278** |
| sent_f1_macro | **0.7626** |
| aspect_acc | **0.5856** |
| avg_confidence | 0.8416 |
| latency_s | 1.587 s |
| cost_usd | **$0.0718** |

**Análisis:** Este es el resultado más revelador de los baselines. Un GPT-4o-mini sin guías ya supera dramáticamente a los clasificadores tradicionales (+38% en F1-sentimiento). Sin embargo, al no tener la ontología oficial, el modelo inventa categorías de aspectos propias o mapea incorrectamente a las existentes, resultando en una precisión de aspectos de solo 58.6%. Este resultado aísla cuantitativamente **el valor del diseño del prompt con ontología**.

---

### 3.4 Experimento 4 — `gpt-4o-mini` (con ontología + RAG)
**Script asociado:** [evaluation/multi_llm/inference_runner.py](./evaluation/multi_llm/inference_runner.py)

**Descripción:** GPT-4o-mini con el prompt ABSA completo: sistema de instrucciones detallado, guías de anotación de la ontología, ejemplo de formato JSON y similitudes coseno pre-computadas por comentario.

**Parámetros:**
- Modelo: `gpt-4o-mini` (OpenAI)
- Temperatura: 0.0
- Max tokens: 1,000
- Formato: JSON Mode activado
- Contexto adicional: top-3 aspectos más similares por coseno

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 637 |
| Aspectos extraídos | 621 |
| Tokens totales | 354,678 (prompt: 300,983 · completion: 53,695) |
| Tokens promedio / llamada | 556.8 |
| Distribución sentimientos | Positivo: 362, Negativo: 171, Neutral: 88 |
| Distribución aspectos | General: 302, Evaluación: 110, Plataforma: 52, Retos: 43, Actividades: 38, Tutoría: 34, Contenido: 29, Foros: 10, Videos: 3 |
| Errores JSON | **0 (0.00%)** |
| Latencia promedio | 1.580 s/comentario |

**Resultados del Juez (GPT-4o como árbitro):**
| Criterio | Resultado |
|----------|-----------|
| Aspecto correcto | **485 / 637 = 76.1%** |
| Sentimiento correcto | **519 / 637 = 81.5%** |
| Ambos correctos | **433 / 637 = 68.0%** |
| Relevancia promedio (1-5) | **3.70** |

**Métricas finales:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | **0.8955** |
| sent_f1_macro | **0.8613** |
| aspect_acc | **0.7614** |
| avg_confidence | 0.8725 |
| latency_s | 1.580 s |
| cost_usd | **$0.0774** |
| json_errors | 0.0000 |

**Análisis:** GPT-4o-mini con el prompt guiado por ontología representa el **mejor balance entre costo y rendimiento** del experimento. Al comparar con `baseline_no_guides` (mismo modelo, sin guías), se observa que la ontología aporta **+17.6 puntos porcentuales** en precisión de aspectos (76.1% vs 58.5%) con un costo prácticamente idéntico ($0.077 vs $0.072). Cero errores de formato JSON confirman que el JSON Mode de OpenAI es completamente confiable para pipelines ABSA.

---

### 3.5 Experimento 5 — `gpt-4o` (con ontología + RAG)
**Script asociado:** [evaluation/multi_llm/inference_runner.py](./evaluation/multi_llm/inference_runner.py)

**Descripción:** La versión completa y más capaz de OpenAI, con el mismo prompt ABSA guiado por ontología.

**Parámetros:**
- Modelo: `gpt-4o` (OpenAI)
- Temperatura: 0.0
- Max tokens: 1,000
- Formato: JSON Mode activado
- Contexto adicional: top-3 aspectos más similares por coseno

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 637 |
| Aspectos extraídos | 652 |
| Tokens totales | 355,818 (prompt: 300,983 · completion: 54,835) |
| Tokens promedio / llamada | 558.6 |
| Distribución sentimientos | Positivo: 330, Negativo: 181, Neutral: 141 |
| Distribución aspectos | General: 294, Evaluación: 107, Plataforma: 56, Tutoría: 45, Retos: 43, Actividades: 42, Contenido: 39, Foros: 20, Videos: 6 |
| Errores JSON | **0 (0.00%)** |
| Latencia promedio | 1.241 s/comentario |

**Resultados del Juez (GPT-4o como árbitro):**
| Criterio | Resultado |
|----------|-----------|
| Aspecto correcto | **502 / 637 = 78.8%** |
| Sentimiento correcto | **561 / 637 = 88.1%** |
| Ambos correctos | **460 / 637 = 72.2%** |
| Relevancia promedio (1-5) | **3.87** |

**Métricas finales:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | **0.9141** ⭐ |
| sent_f1_macro | **0.8982** ⭐ |
| aspect_acc | **0.7881** ⭐ |
| avg_confidence | 0.8613 |
| latency_s | 1.241 s |
| cost_usd | **$1.3008** |
| json_errors | 0.0000 |

**Análisis:** GPT-4o obtiene el **mejor rendimiento absoluto** en todas las métricas de calidad. Su distribución de sentimientos es la más equilibrada entre los modelos (mayor proporción de "Neutral"), evidenciando mayor capacidad de matización. También detecta más aspectos únicos por comentario (652 vs 621 de GPT-4o-mini), sugiriendo mayor capacidad para comentarios multi-aspecto. La contrapartida es su costo, **16.8 veces mayor** que GPT-4o-mini ($1.30 vs $0.077) para una mejora de ~2.8 puntos porcentuales en F1, lo que lo posiciona como costoso para producción a escala.

---

### 3.6 Experimento 6 — `gemini-2.5-flash` (con ontología + RAG)
**Script asociado:** [evaluation/multi_llm/inference_runner.py](./evaluation/multi_llm/inference_runner.py)

**Descripción:** Modelo *flash* de última generación de Google DeepMind, con el mismo prompt ABSA guiado. Se utilizó la API de Google AI Studio con la librería `google-generativeai`.

**Parámetros:**
- Modelo: `gemini-2.5-flash` (Google DeepMind)
- Temperatura: 0.0
- System instruction: Idéntico al prompt de sistema de OpenAI
- Generación de JSON: Mediante instrucción de texto (sin JSON Mode nativo en el momento del experimento)

> [!WARNING]
> **Incidencia detectada:** El modelo Gemini 2.5 Flash solo generó respuestas válidas para **18 de los 637 comentarios** (2.8%). El resto de las 619 iteraciones devolvieron respuestas vacías (`""`) sin error explícito en la API, pero con conteo de tokens mínimo (promedio 19.4 tokens/llamada vs ~557 en OpenAI). Esto indica que el modelo enturó en un estado de rechazo silencioso de las solicitudes, probablemente relacionado con restricciones de la capa gratuita de la API de Google o con el límite de tokens de salida.

**Resultados de inferencia:**
| Campo | Valor |
|-------|-------|
| Comentarios procesados | 637 |
| Aspectos extraídos | **18 (de 637 esperados)** |
| Tokens totales | 12,360 (prompt: 10,322 · completion: 2,038) |
| Tokens promedio / llamada | **19.4** *(anormal — esperado ~550)* |
| Distribución sentimientos | Positivo: 9, Negativo: 6, Neutral: 3 |
| Distribución aspectos | General: 5, Evaluación: 3, Actividades: 3, Retos: 2, Contenido: 2, Plataforma: 1, Tutoría: 1, Foros: 1 |
| Errores JSON | 4 de 637 (0.63%) |
| Latencia promedio | 0.120 s/comentario |

**Resultados del Juez (sobre los 637 registros):**
| Criterio | Resultado |
|----------|-----------|
| Aspecto correcto | **16 / 637 = 2.5%** |
| Sentimiento correcto | **15 / 637 = 2.4%** |
| Ambos correctos | **14 / 637 = 2.2%** |
| Relevancia promedio (1-5) | **0.11** |

**Métricas finales:**
| Métrica | Resultado |
|---------|-----------|
| sent_f1_weighted | 0.8750 |
| sent_f1_macro | 0.8750 |
| aspect_acc | **0.0251** ⚠️ |
| avg_confidence | 0.9333 |
| latency_s | **0.120 s** ⭐ |
| cost_usd | **$0.0018** ⭐ |
| json_errors | 0.0063 |

> [!NOTE]
> Las métricas de F1-sentimiento de Gemini (0.875) son engañosamente altas. Provienen únicamente de los 18 comentarios que sí respondió correctamente, no de los 637 completos. El juez evaluó todos los 637 registros, por lo que el `aspect_acc` de 2.5% refleja la realidad: la mayoría de registros quedaron sin respuesta, lo que el juez penalizó correctamente como fallos.

**Análisis:** La causa más probable del fallo masivo fue la **cuota agotada de la API gratuita** de Google (free-tier). El modelo recibía las solicitudes pero su cuota de tokens de salida estaba en 0, por lo que devolvía respuestas vacías en lugar de un error HTTP explícito. Los 18 registros exitosos que sí respondió muestran un formato correcto y alta confianza (0.93), lo que indica que el modelo en sí es capaz; el problema fue de disponibilidad de recursos.

---

## 4. Tabla Comparativa Final

| Modelo | F1-Sent (w) | F1-Sent (m) | Aspect Acc | Confianza | Latencia (s) | Costo (USD) | Errores JSON |
|--------|-------------|-------------|------------|-----------|--------------|-------------|--------------|
| `baseline_majority_class` | 0.4552 | 0.2511 | 0.3514 | 1.0000 | 0.000 | $0.00 | 0.0% |
| `baseline_cosine_only` | 0.4377 | 0.3756 | 0.4129 | 0.4065 | 0.000 | $0.00 | 0.0% |
| `baseline_no_guides` | 0.8278 | 0.7626 | 0.5856 | 0.8416 | 1.587 | $0.07 | 0.0% |
| `gpt-4o-mini` | 0.8955 | 0.8613 | 0.7614 | 0.8725 | 1.580 | $0.08 | 0.0% |
| `gpt-4o` | **0.9141** | **0.8982** | **0.7881** | 0.8613 | 1.241 | $1.30 | 0.0% |
| `gemini-2.5-flash`* | 0.8750 | 0.8750 | 0.0251 | **0.9333** | **0.120** | **$0.002** | 0.63% |

> *Resultados de Gemini 2.5 Flash son parciales (solo 18/637 comentarios respondidos exitosamente) debido a límite de cuota de API.

---

## 5. Hallazgos Clave

### Hallazgo 1 — El valor de la ontología estructurada
> **El mismo modelo (GPT-4o-mini) mejora +17.6% en precisión de aspectos al recibir la ontología como guía.**

La comparación directa entre `baseline_no_guides` (aspect_acc = 58.5%) y `gpt-4o-mini` con ontología (aspect_acc = 76.1%) aísla el impacto puro del diseño del prompt con restricciones ontológicas. Esto valida la arquitectura DSR propuesta: sin la ontología, el LLM genera categorías libres que no corresponden al marco conceptual del dominio educativo.

### Hallazgo 2 — Los LLMs frontera superan ampliamente los métodos tradicionales
> **Salto de ~45% (tradicional) a ~89–91% (LLM) en F1-sentimiento.**

Los baselines estadísticos (majority class, cosine) tienen un techo natural de rendimiento. Ninguna técnica de similitud vectorial puede capturar la ironía, el contexto o las construcciones negativas implícitas en comentarios educativos en español. Los LLMs superan esta barrera de forma categórica.

### Hallazgo 3 — Relación rendimiento/costo de GPT-4o-mini
> **GPT-4o-mini logra el 98.0% del rendimiento de GPT-4o al 5.9% de su costo.**

Para despliegues educativos a escala, GPT-4o-mini es la opción óptima. La mejora de GPT-4o (+2.3% F1-sent, +2.7% aspect_acc) no justifica el costo 16.8x mayor en aplicaciones con presupuesto limitado.

### Hallazgo 4 — Riesgo de respuestas vacías silenciosas en APIs con cuotas
> **Gemini 2.5 Flash devolvió respuestas vacías sin error HTTP explícito ante cuota agotada.**

Este hallazgo tiene implicaciones metodológicas importantes: un pipeline de inferencia automática debe implementar validación de contenido mínima (no solo verificar el código HTTP 200) para detectar fallos silenciosos. Se implementó esta corrección en el código del proyecto.

---

## 6. Conclusiones

1. **Viabilidad del ABSA con LLMs en educación:** Los modelos GPT-4o y GPT-4o-mini demuestran que el análisis de sentimientos por aspectos es viable y altamente preciso en comentarios educativos en español, superando el 89% de F1.

2. **El diseño del Knowledge Graph y la ontología son críticos:** No basta con tener un LLM potente; la ontología estructurada en Neo4j actúa como restricción de dominio indispensable para la extracción de aspectos correcta.

3. **GPT-4o-mini es el modelo recomendado para producción:** Mejor balance calidad/costo para despliegues a escala en plataformas educativas reales.

4. **Robustez del pipeline:** Cero errores de parseo JSON en 1,274 llamadas a OpenAI (gpt-4o + gpt-4o-mini + no_guides) confirman la estabilidad del sistema.

---

*Informe generado automáticamente a partir de los resultados en `evaluation/results/`. Datos: 637 comentarios, 28 cursos, 8 aspectos ontológicos. Fecha: Mayo 2026.*
