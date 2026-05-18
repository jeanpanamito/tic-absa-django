# Guía de Usuario - TIC ABSA Graph

## Índice

1. [Introducción](#introducción)
2. [Instalación y Configuración](#instalación-y-configuración)
3. [Uso Básico](#uso-básico)
4. [Análisis de Datos](#análisis-de-datos)
5. [Interpretación de Resultados](#interpretación-de-resultados)
6. [Troubleshooting](#troubleshooting)
7. [Ejemplos Prácticos](#ejemplos-prácticos)
8. [FAQ](#faq)

## Introducción

TIC ABSA Graph es una herramienta diseñada para procesar comentarios educativos y prepararlos para el análisis de sentimientos basado en aspectos (ABSA). Esta guía te ayudará a utilizar el sistema de manera efectiva.

### ¿Qué hace el sistema?

- **Procesa comentarios educativos** desde archivos JSON
- **Limpia y estructura** los datos para análisis
- **Identifica entidades** (cursos, autores, comentarios, hilos)
- **Extrae relaciones** entre entidades
- **Genera visualizaciones** para análisis exploratorio
- **Exporta datos** en formatos compatibles con herramientas de grafos

### Casos de Uso

- Análisis de engagement en cursos online
- Identificación de temas recurrentes en discusiones
- Análisis de sentimientos en comentarios educativos
- Construcción de grafos de conocimiento para investigación educativa

## Instalación y Configuración

### Requisitos del Sistema

- **Python**: 3.8 o superior
- **Memoria RAM**: Mínimo 4GB (recomendado 8GB+)
- **Espacio en disco**: Suficiente para almacenar el dataset y archivos exportados

### Instalación de Dependencias

```bash
# Instalar paquetes requeridos
pip install pandas matplotlib tqdm numpy

# Verificar instalación
python -c "import pandas, matplotlib, tqdm, numpy; print('Todas las dependencias instaladas correctamente')"
```

### Preparación de Datos

1. **Formato de entrada**: El sistema espera archivos JSON con estructura específica
2. **Ubicación**: Coloca tu archivo JSON en una ubicación accesible
3. **Tamaño**: Para datasets grandes, considera usar muestreo inicial

## Uso Básico

### Paso 1: Importar y Configurar

```python
# Importar la clase principal
from src.preprocessing.comment_preprocessor import CommentPreprocessor

# Configurar el preprocesador
file_path = "ruta/a/tu/archivo.json"
sample_size = None  # None para procesar todos los datos, o un número para muestra

preprocessor = CommentPreprocessor(file_path, sample_size=sample_size)
```

### Paso 2: Cargar Datos

```python
# Cargar los datos
df = preprocessor.load_data()

# Verificar la carga
print(f"Datos cargados: {len(df)} registros")
print(f"Columnas disponibles: {list(df.columns)}")
```

### Paso 3: Preprocesar Datos

```python
# Realizar preprocesamiento completo
df_processed = preprocessor.preprocess_data()

# Verificar campos nuevos
new_columns = ['body_cleaned', 'votes_up', 'votes_down', 'votes_total',
               'created_at', 'updated_at', 'is_thread', 'is_comment',
               'parent_id', 'comment_thread_id', 'text_length', 'word_count']

print("Campos generados:")
for col in new_columns:
    if col in df_processed.columns:
        print(f"✓ {col}")
```

### Paso 4: Analizar Calidad

```python
# Analizar calidad de datos
stats = preprocessor.analyze_data_quality()

# Mostrar estadísticas principales
print(f"Total de registros: {stats['total_records']:,}")
print(f"Comentarios: {stats['comments']:,}")
print(f"Hilos de discusión: {stats['threads']:,}")
print(f"Autores únicos: {stats['unique_authors']:,}")
print(f"Cursos únicos: {stats['unique_courses']:,}")
```

### Paso 5: Identificar Entidades

```python
# Identificar entidades para el grafo
graph_data = preprocessor.identify_graph_entities()

# Mostrar resumen
print("Entidades identificadas:")
for entity_type, items in graph_data['entities'].items():
    print(f"- {entity_type}: {len(items):,}")

print("\nRelaciones identificadas:")
for rel_type, pairs in graph_data['relations'].items():
    print(f"- {rel_type.replace('_', ' ').title()}: {len(pairs):,}")
```

### Paso 6: Generar Visualizaciones

```python
# Generar visualizaciones
preprocessor.visualize_data_distribution()
```

### Paso 7: Exportar Datos

```python
# Exportar en formato CSV
preprocessor.export_graph_data(format='csv')

# Exportar en formato JSON
preprocessor.export_graph_data(format='json')
```

## Análisis de Datos

### Exploración Inicial

```python
# Explorar ejemplos de hilos
threads_sample = df_processed[df_processed['is_thread']].head(3)
for _, thread in threads_sample.iterrows():
    print(f"Hilo: {thread.get('title', 'Sin título')}")
    print(f"Curso: {thread['course_id']}")
    print(f"Autor: {thread['author_username']}")
    print("=" * 50)

# Explorar ejemplos de comentarios
comments_sample = df_processed[df_processed['is_comment']].head(3)
for _, comment in comments_sample.iterrows():
    print(f"Texto: {comment['body_cleaned'][:100]}...")
    print(f"Palabras: {comment['word_count']}")
    print(f"Votos: {comment['votes_total']}")
    print("=" * 50)
```

### Análisis de Relaciones

```python
# Top autores más activos
top_authors = df_processed['author_username'].value_counts().head(10)
print("Top 10 autores más activos:")
for author, count in top_authors.items():
    print(f"  {author}: {count} comentarios")

# Top cursos con más comentarios
top_courses = df_processed['course_id'].value_counts().head(10)
print("\nTop 10 cursos con más comentarios:")
for course, count in top_courses.items():
    print(f"  {course}: {count} comentarios")

# Análisis de respuestas
replies = df_processed[df_processed['parent_id'].notna()]
print(f"\nComentarios que son respuestas: {len(replies):,}")
print(f"Porcentaje de respuestas: {len(replies)/len(df_processed)*100:.1f}%")
```

### Generación de Esquema

```python
# Generar esquema del grafo
schema = preprocessor.generate_graph_schema()

# Mostrar esquema detallado
for class_name, class_info in schema['classes'].items():
    print(f"\n🔷 Clase: {class_name}")
    print(f"  Propiedades: {', '.join(class_info['properties'])}")
    print(f"  Relaciones: {', '.join(class_info['relations'])}")
```

## Interpretación de Resultados

### Estadísticas del Dataset

Basado en el análisis del dataset de ejemplo:

- **182,500 registros totales**: Dataset considerable para análisis
- **117,906 comentarios (64.6%)**: Mayoría son comentarios individuales
- **64,594 hilos (35.4%)**: Estructura de discusión bien definida
- **49,633 autores únicos**: Comunidad diversa y activa
- **455 cursos únicos**: Variedad de contenido educativo

### Indicadores de Calidad

**Datos completos:**
- 0% de comentarios sin cuerpo de texto
- 0% de comentarios sin autor
- 0% de comentarios sin curso asociado

**Métricas de engagement:**
- Longitud promedio: 248 caracteres (comentarios sustanciales)
- Palabras promedio: 41.3 (contenido significativo)
- Votos promedio: 0.08 (bajo engagement en votos)

### Patrones de Actividad

**Autores más activos:**
- LeninCamacho (2,407 comentarios): Usuario muy activo
- mariadelcisne (1,786 comentarios): Participación consistente
- mrramirez (1,564 comentarios): Alto nivel de engagement

**Cursos más populares:**
- GPSY3 (8,889 comentarios): Curso con mayor discusión
- PRESCHEDU3 (6,226 comentarios): Alto interés estudiantil
- ADMINI3 (6,050 comentarios): Contenido que genera debate

### Estructura de Discusión

- **13.8% de respuestas**: Indica discusiones moderadamente interactivas
- **Relaciones bien definidas**: Estructura jerárquica clara
- **Metadatos completos**: Información temporal y de autoría disponible

## Troubleshooting

### Problemas Comunes

#### 1. Error al cargar archivo JSON

**Síntoma:**
```
Error: Archivo no encontrado en /ruta/al/archivo.json
```

**Solución:**
- Verificar que la ruta del archivo sea correcta
- Asegurar que el archivo existe y es accesible
- Usar rutas absolutas si es necesario

#### 2. Error de memoria insuficiente

**Síntoma:**
```
MemoryError: Unable to allocate array
```

**Solución:**
- Usar muestreo: `sample_size=10000`
- Cerrar otras aplicaciones que consuman memoria
- Procesar en lotes más pequeños

#### 3. Columnas faltantes

**Síntoma:**
```
Advertencia: La columna 'body' no se encontró en los datos
```

**Solución:**
- Verificar la estructura del JSON
- Asegurar que las columnas esperadas estén presentes
- Adaptar el código para la estructura específica de tus datos

#### 4. Fechas no válidas

**Síntoma:**
```
Date Range: (NaT, NaT)
```

**Solución:**
- Verificar el formato de fechas en el JSON
- Ajustar el parser de fechas según el formato
- Considerar fechas como texto si no se pueden parsear

### Optimización de Rendimiento

#### Para Datasets Grandes

```python
# Usar muestreo para análisis inicial
preprocessor = CommentPreprocessor(file_path, sample_size=10000)

# Procesar en lotes
batch_size = 5000
for i in range(0, len(df), batch_size):
    batch = df[i:i+batch_size]
    # Procesar batch
```

#### Para Análisis Exploratorio

```python
# Usar solo campos esenciales
essential_columns = ['_id', 'body', 'author_username', 'course_id', '_type']
df_subset = df[essential_columns]
```

## Ejemplos Prácticos

### Ejemplo 1: Análisis Rápido

```python
# Configuración rápida para análisis exploratorio
preprocessor = CommentPreprocessor("datos.json", sample_size=5000)
df = preprocessor.load_data()
df_processed = preprocessor.preprocess_data()
stats = preprocessor.analyze_data_quality()

print("Análisis rápido completado:")
print(f"- {stats['total_records']} registros procesados")
print(f"- {stats['unique_authors']} autores únicos")
print(f"- {stats['unique_courses']} cursos únicos")
```

### Ejemplo 2: Análisis de Cursos Específicos

```python
# Filtrar por curso específico
curso_especifico = "course-v1:UTPL+GPSY3+2020_1"
df_curso = df_processed[df_processed['course_id'] == curso_especifico]

print(f"Análisis del curso {curso_especifico}:")
print(f"- Total comentarios: {len(df_curso)}")
print(f"- Autores únicos: {df_curso['author_username'].nunique()}")
print(f"- Longitud promedio: {df_curso['text_length'].mean():.1f} caracteres")
```

### Ejemplo 3: Análisis de Autores Activos

```python
# Identificar autores muy activos
autores_activos = df_processed['author_username'].value_counts()
autores_top = autores_activos[autores_activos > 100]

print("Autores con más de 100 comentarios:")
for autor, count in autores_top.head(10).items():
    print(f"- {autor}: {count} comentarios")
```

### Ejemplo 4: Análisis Temporal

```python
# Análisis por fechas (si están disponibles)
if 'created_at' in df_processed.columns:
    df_processed['created_at'] = pd.to_datetime(df_processed['created_at'])
    
    # Comentarios por mes
    df_processed['mes'] = df_processed['created_at'].dt.to_period('M')
    comentarios_por_mes = df_processed['mes'].value_counts().sort_index()
    
    print("Comentarios por mes:")
    for mes, count in comentarios_por_mes.head(12).items():
        print(f"- {mes}: {count} comentarios")
```

## FAQ

### Preguntas Generales

**Q: ¿Qué formato de archivo necesito?**
A: El sistema requiere archivos JSON con estructura específica de MongoDB, incluyendo campos como `_id`, `body`, `author_username`, `course_id`, `_type`, etc.

**Q: ¿Puedo usar archivos CSV en lugar de JSON?**
A: Actualmente el sistema está diseñado para JSON. Para CSV, necesitarías adaptar el código de carga de datos.

**Q: ¿Cuánto tiempo toma procesar mi dataset?**
A: Depende del tamaño. Para 182,500 registros toma aproximadamente 5-10 minutos. Usa `sample_size` para pruebas rápidas.

### Preguntas Técnicas

**Q: ¿Qué hago si mi JSON tiene una estructura diferente?**
A: Adapta el método `load_data()` para tu estructura específica, o preprocesa tu JSON para que coincida con el formato esperado.

**Q: ¿Puedo procesar múltiples archivos?**
A: Sí, puedes crear múltiples instancias de `CommentPreprocessor` o modificar el código para procesar múltiples archivos.

**Q: ¿Cómo exporto solo ciertas entidades?**
A: Modifica el método `export_graph_data()` para exportar solo las entidades que necesites.

### Preguntas sobre Resultados

**Q: ¿Qué significan los valores NaN en las fechas?**
A: Indica que las fechas no se pudieron parsear correctamente. Verifica el formato de fechas en tu JSON.

**Q: ¿Por qué hay tan pocos votos promedio?**
A: Es normal en plataformas educativas. Los usuarios suelen participar más en discusiones que en votar.

**Q: ¿Cómo interpreto las relaciones del grafo?**
A: Las relaciones muestran conexiones entre entidades. Por ejemplo, `author_posted_comment` conecta cada autor con sus comentarios.

### Preguntas sobre Visualizaciones

**Q: ¿Puedo personalizar las visualizaciones?**
A: Sí, modifica el método `visualize_data_distribution()` para cambiar colores, tamaños, o agregar nuevos gráficos.

**Q: ¿Cómo guardo las visualizaciones?**
A: Agrega `plt.savefig('nombre_archivo.png')` antes de `plt.show()`.

**Q: ¿Puedo generar visualizaciones específicas?**
A: Sí, puedes crear métodos adicionales para visualizaciones específicas como análisis temporal o distribución por curso.

### Preguntas sobre Exportación

**Q: ¿Qué formato es mejor para mi caso de uso?**
A: CSV es mejor para análisis en Excel/SPSS, JSON es mejor para integración con otras herramientas de programación.

**Q: ¿Puedo exportar solo ciertas relaciones?**
A: Sí, modifica el método de exportación para incluir solo las relaciones que necesites.

**Q: ¿Cómo importo los datos exportados en otras herramientas?**
A: Los archivos CSV se pueden abrir en Excel, R, o pandas. El JSON se puede usar en Neo4j, NetworkX, o herramientas similares.
