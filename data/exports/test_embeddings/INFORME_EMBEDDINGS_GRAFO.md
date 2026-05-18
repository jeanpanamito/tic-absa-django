# Informe de Análisis: Embeddings del Grafo con Node2Vec

**Fecha de generación:** 2024-12-19  
**Script utilizado:** `src/absa/test_graph_embeddings.py`  
**Ontología:** 9 aspectos educativos con 10 relaciones semánticas

---

## 1. Resumen Ejecutivo

Este informe presenta el análisis comparativo de embeddings generados mediante Node2Vec sobre el grafo de conocimiento de aspectos educativos, evaluando tres configuraciones dimensionales: **128, 200 y 300 dimensiones**.

### 1.1 Objetivos
- Generar embeddings del grafo con diferentes dimensionalidades
- Analizar la calidad y características de los embeddings
- Visualizar las relaciones semánticas entre aspectos
- Comparar el rendimiento entre diferentes configuraciones

### 1.2 Metodología
- **Algoritmo:** Node2Vec
- **Parámetros:** walk_length=30, num_walks=200, workers=4, p=1, q=1
- **Aspectos analizados:** 9 (Actividades, Contenido, Evaluacion, Foros, General, Plataforma, Retos, Tutoria, Videos)
- **Métricas:** Similitud coseno, PCA, t-SNE, estadísticas descriptivas

---

## 2. Análisis de Estadísticas Descriptivas

### 2.1 Estadísticas Globales por Dimensión

| Dimensión | Media | Desv. Estándar | Mínimo | Máximo | Mediana |
|-----------|-------|----------------|--------|--------|---------|
| **128D** | 0.0009 | 0.1850 | -0.5586 | 0.5736 | -0.0023 |
| **200D** | 0.0050 | 0.1479 | -0.4696 | 0.5473 | 0.0018 |
| **300D** | 0.0078 | 0.1214 | -0.4040 | 0.3847 | 0.0013 |

**Observaciones:**
- La desviación estándar **disminuye** con el aumento de dimensiones (0.185 → 0.148 → 0.121), indicando mayor estabilidad.
- El rango de valores se **reduce** con más dimensiones, sugiriendo una distribución más compacta.
- La media se mantiene cercana a cero en todas las configuraciones, indicando una distribución centrada.

### 2.2 Análisis por Aspecto

#### Aspecto "General" - Caso Especial
El aspecto "General" muestra características únicas en todas las dimensiones:

| Dimensión | Norma L2 | Desv. Estándar | Observación |
|-----------|----------|----------------|-------------|
| 128D | 0.049 | 0.004 | Embedding muy pequeño, casi nulo |
| 200D | 0.043 | 0.003 | Similar a 128D |
| 300D | 0.032 | 0.002 | Aún más pequeño |

**Interpretación:** El aspecto "General" tiene un embedding prácticamente nulo, lo que sugiere que:
- No tiene conexiones fuertes en el grafo
- Es un nodo aislado o con pocas relaciones
- Puede requerir revisión en la ontología

#### Aspectos con Mayor Magnitud (Norma L2)

**128 Dimensiones:**
1. Actividades: 2.909
2. Foros: 2.880
3. Videos: 2.266
4. Retos: 2.180
5. Contenido: 2.045

**200 Dimensiones:**
1. Actividades: 2.908
2. Foros: 2.814
3. Videos: 2.243
4. Contenido: 2.169
5. Evaluacion: 2.117

**300 Dimensiones:**
1. Actividades: 2.918
2. Foros: 2.848
3. Videos: 2.287
4. Contenido: 2.185
5. Evaluacion: 2.088

**Patrón observado:** Los aspectos con mayor magnitud son consistentes entre dimensiones, sugiriendo que tienen representaciones más ricas en el grafo.

---

## 3. Análisis de Similitudes Semánticas

### 3.1 Relaciones Más Fuertes (Similitud > 0.9)

#### 128 Dimensiones:
- **Evaluacion ↔ Retos:** 0.957 (relación padre-hijo)
- **Contenido ↔ Videos:** 0.973 (relación padre-hijo)
- **Actividades ↔ Foros:** 0.968 (relación padre-hijo)

#### 200 Dimensiones:
- **Evaluacion ↔ Retos:** 0.963
- **Contenido ↔ Videos:** 0.986
- **Actividades ↔ Foros:** 0.975

#### 300 Dimensiones:
- **Evaluacion ↔ Retos:** 0.971
- **Contenido ↔ Videos:** 0.990
- **Actividades ↔ Foros:** 0.981

**Conclusión:** Las relaciones jerárquicas (padre-hijo) muestran las similitudes más altas, lo cual es esperado y valida la estructura de la ontología.

### 3.2 Relaciones Moderadas (0.7 - 0.9)

**Aspectos consistentemente relacionados:**
- **Evaluacion ↔ Tutoria:** ~0.90 (relación "ayuda_en")
- **Retos ↔ Tutoria:** ~0.92 (relación indirecta)
- **Contenido ↔ Plataforma:** ~0.65-0.67 (relación "soporta")
- **Videos ↔ Plataforma:** ~0.70 (relación indirecta)

### 3.3 Aspecto "General" - Aislamiento

El aspecto "General" muestra similitudes muy bajas o negativas con todos los demás aspectos:

| Dimensión | Similitud Promedio | Rango |
|-----------|-------------------|-------|
| 128D | -0.075 | [-0.106, 0.008] |
| 200D | 0.060 | [-0.050, 0.152] |
| 300D | -0.013 | [-0.078, 0.116] |

**Recomendación:** Revisar la definición y relaciones del aspecto "General" en la ontología.

### 3.4 Estabilidad entre Dimensiones

Las similitudes se mantienen **consistentes** entre las tres configuraciones dimensionales, con variaciones menores al 5% en la mayoría de los casos. Esto indica que:
- Los embeddings capturan relaciones estables
- El aumento de dimensiones no cambia significativamente las relaciones semánticas
- La estructura del grafo se preserva independientemente de la dimensionalidad

---

## 4. Análisis de Reducción Dimensional (PCA)

### 4.1 Varianza Explicada

| Dimensión | PC1 (%) | PC2 (%) | Total (%) |
|-----------|---------|---------|-----------|
| **128D** | 53.82 | 21.93 | 75.75 |
| **200D** | 53.38 | 24.30 | 77.68 |
| **300D** | 49.35 | 25.51 | 74.86 |

**Observaciones:**
- La primera componente principal explica aproximadamente **50-54%** de la varianza
- La segunda componente explica **22-26%** de la varianza
- El total de las dos primeras componentes explica **~75%** de la varianza
- **200D** muestra el mejor balance con mayor varianza explicada total

### 4.2 Agrupaciones en el Espacio PCA

**Grupo 1: Actividades y Foros** (PC1 positivo, PC2 cercano a cero)
- Relación padre-hijo fuerte
- Ubicados en el mismo cuadrante en todas las dimensiones

**Grupo 2: Contenido y Videos** (PC1 negativo, PC2 variable)
- Relación padre-hijo muy fuerte
- Agrupación consistente

**Grupo 3: Evaluacion, Retos y Tutoria** (PC1 negativo, PC2 positivo)
- Relaciones jerárquicas y semánticas fuertes
- Forman un cluster coherente

**Grupo 4: Plataforma** (PC1 variable, PC2 negativo)
- Posición intermedia, relacionado con múltiples aspectos

**Grupo 5: General** (cerca del origen)
- Prácticamente en el centro, confirmando su carácter genérico

---

## 5. Comparación entre Dimensionalidades

### 5.1 Ventajas de 128 Dimensiones
- ✅ Menor costo computacional
- ✅ Embeddings más compactos
- ✅ Suficiente para capturar relaciones principales
- ✅ Varianza explicada razonable (75.75%)

### 5.2 Ventajas de 200 Dimensiones
- ✅ Mejor balance entre precisión y eficiencia
- ✅ Mayor varianza explicada en PCA (77.68%)
- ✅ Similitudes más estables
- ✅ **Recomendado para producción**

### 5.3 Ventajas de 300 Dimensiones
- ✅ Mayor capacidad de representación
- ✅ Mejor separación en algunas relaciones
- ⚠️ Mayor costo computacional
- ⚠️ Varianza explicada similar a 128D (74.86%)

### 5.4 Recomendación

**Dimensión óptima: 200 dimensiones**

**Justificación:**
1. Mejor varianza explicada en PCA
2. Similitudes más estables y precisas
3. Balance óptimo entre capacidad y eficiencia
4. Consistencia en las relaciones semánticas

---

## 6. Hallazgos Clave

### 6.1 Validación de la Ontología
✅ Las relaciones jerárquicas (padre-hijo) muestran similitudes muy altas (>0.95)  
✅ Las relaciones semánticas definidas se reflejan en los embeddings  
✅ La estructura del grafo se preserva correctamente

### 6.2 Aspectos Problemáticos
⚠️ **General:** Embedding prácticamente nulo, requiere revisión  
⚠️ **Plataforma:** Relaciones moderadas pero consistentes

### 6.3 Estabilidad
✅ Los embeddings son estables entre diferentes dimensionalidades  
✅ Las relaciones semánticas se mantienen consistentes  
✅ La estructura jerárquica se preserva correctamente

---

## 7. Conclusiones

1. **Node2Vec genera embeddings de calidad** que capturan correctamente las relaciones del grafo de conocimiento.

2. **200 dimensiones es la configuración óptima** para este caso de uso, balanceando precisión y eficiencia.

3. **La estructura jerárquica de la ontología** se refleja correctamente en los embeddings, con relaciones padre-hijo mostrando similitudes muy altas.

4. **El aspecto "General" requiere atención**, ya que su embedding es prácticamente nulo, sugiriendo que necesita más relaciones en el grafo.

5. **Los embeddings son estables** entre diferentes configuraciones dimensionales, lo que indica robustez del modelo.

---

## 8. Recomendaciones

### 8.1 Para la Ontología
- Revisar y enriquecer las relaciones del aspecto "General"
- Considerar agregar más relaciones semánticas entre aspectos relacionados
- Validar que todas las relaciones definidas se reflejen en el grafo

### 8.2 Para el Pipeline ABSA
- Utilizar **200 dimensiones** como configuración por defecto
- Considerar normalizar los embeddings antes de la fusión
- Implementar validación de similitudes mínimas para filtrar relaciones débiles

### 8.3 Para Futuras Investigaciones
- Experimentar con diferentes valores de p y q en Node2Vec
- Evaluar el impacto de más relaciones en el grafo
- Comparar con otros algoritmos de embeddings de grafos (GraphSAGE, GCN)

---

## 9. Archivos Generados

### Por cada dimensión (128, 200, 300):
- `matriz_embeddings_{dim}d.csv` - Matriz completa de embeddings
- `heatmap_embeddings_{dim}d.png` - Visualización de la matriz
- `matriz_similitudes_{dim}d.csv` - Matriz de similitudes coseno
- `similitudes_{dim}d.png` - Heatmap de similitudes
- `estadisticas_embeddings_{dim}d.json` - Estadísticas descriptivas
- `estadisticas_resumen_{dim}d.csv` - Tabla de estadísticas
- `pca_coordenadas_{dim}d.csv` - Coordenadas PCA
- `pca_visualizacion_{dim}d.png` - Visualización PCA 2D
- `tsne_coordenadas_{dim}d.csv` - Coordenadas t-SNE
- `tsne_visualizacion_{dim}d.png` - Visualización t-SNE 2D

---

**Fin del Informe**

