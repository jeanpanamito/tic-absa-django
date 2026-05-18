# Documentación Técnica - TIC ABSA Graph

## Índice

1. [Arquitectura del Sistema](#arquitectura-del-sistema)
2. [Clase CommentPreprocessor](#clase-commentpreprocessor)
3. [Proceso de Preprocesamiento](#proceso-de-preprocesamiento)
4. [Esquema del Grafo de Conocimiento](#esquema-del-grafo-de-conocimiento)
5. [Análisis de Datos](#análisis-de-datos)
6. [Exportación de Datos](#exportación-de-datos)
7. [Visualizaciones](#visualizaciones)
8. [Consideraciones Técnicas](#consideraciones-técnicas)

## Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                    CommentPreprocessor                      │
├─────────────────────────────────────────────────────────────┤
│  • load_data()           • preprocess_data()               │
│  • analyze_data_quality() • identify_graph_entities()      │
│  • generate_graph_schema() • export_graph_data()           │
│  • visualize_data_distribution()                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DataFrame (pandas)                      │
├─────────────────────────────────────────────────────────────┤
│  • Datos originales      • Datos procesados                │
│  • Metadatos extraídos   • Entidades identificadas         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Graph Data Structure                     │
├─────────────────────────────────────────────────────────────┤
│  • entities: {courses, authors, comments, threads}         │
│  • relations: {author_posted_comment, comment_belongs_to_  │
│    thread, comment_about_course, reply_to_comment}         │
└─────────────────────────────────────────────────────────────┘
```

## Clase CommentPreprocessor

### Constructor

```python
def __init__(self, file_path: str, sample_size: Optional[int] = None):
```

**Parámetros:**
- `file_path`: Ruta al archivo JSON con los comentarios
- `sample_size`: Número de registros a muestrear (None para todos)

**Atributos:**
- `self.file_path`: Ruta del archivo de datos
- `self.sample_size`: Tamaño de la muestra
- `self.df`: DataFrame con los datos procesados
- `self.graph_ready_data`: Datos estructurados para el grafo
- `self.stats`: Estadísticas de calidad de datos

### Métodos Principales

#### 1. load_data()

Carga los datos JSON y los convierte a DataFrame.

**Funcionalidad:**
- Lectura del archivo JSON
- Manejo de diferentes estructuras JSON
- Muestreo opcional de datos
- Validación de formato

**Manejo de Errores:**
- FileNotFoundError: Archivo no encontrado
- JSONDecodeError: Error en formato JSON
- Exception: Errores generales

#### 2. _clean_text()

Limpia el texto de un comentario.

**Procesos:**
- Eliminación de URLs y menciones
- Limpieza de caracteres especiales
- Normalización de espacios
- Preservación de caracteres acentuados

#### 3. preprocess_data()

Realiza el preprocesamiento completo de los datos.

**Pasos:**
1. Limpieza de texto (`body_cleaned`)
2. Extracción de metadatos de votos
3. Normalización de fechas
4. Identificación de tipos de registro
5. Extracción de relaciones parent-child
6. Cálculo de métricas de texto

**Campos Generados:**
- `body_cleaned`: Texto limpio
- `votes_up`, `votes_down`, `votes_total`: Métricas de votos
- `created_at`, `updated_at`: Fechas normalizadas
- `is_thread`, `is_comment`: Identificación de tipos
- `parent_id`, `comment_thread_id`: Relaciones
- `text_length`, `word_count`: Métricas de texto

## Proceso de Preprocesamiento

### 1. Limpieza de Texto

```python
def _clean_text(self, text: str) -> str:
    # Eliminar URLs y menciones
    text = re.sub(r'http\S+|@\S+', ' ', text)
    
    # Limpiar caracteres especiales (preservar acentos)
    text = re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑ.,;!?]', ' ', text)
    
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
```

### 2. Extracción de Metadatos

**Votos:**
```python
self.df['votes_up'] = self.df['votes'].apply(
    lambda x: x.get('up_count', 0) if isinstance(x, dict) else 0
)
```

**Fechas:**
```python
def parse_date(date_dict):
    if isinstance(date_dict, dict) and '$date' in date_dict:
        try:
            return datetime.strptime(date_dict['$date'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except:
            return pd.NaT
    return pd.NaT
```

### 3. Identificación de Tipos

```python
self.df['is_thread'] = self.df['_type'] == 'CommentThread'
self.df['is_comment'] = self.df['_type'] == 'Comment'
```

## Esquema del Grafo de Conocimiento

### Entidades

#### 1. Course
```json
{
  "id": "course_id",
  "properties": ["course_id", "name", "description"],
  "relations": ["hasComment", "hasThread"]
}
```

#### 2. Author
```json
{
  "id": "username",
  "properties": ["username", "activity_level"],
  "relations": ["postedComment", "startedThread"]
}
```

#### 3. Comment
```json
{
  "id": "_id.$oid",
  "properties": ["text", "word_count", "votes", "created_at"],
  "relations": ["aboutCourse", "inThread", "replyTo"]
}
```

#### 4. Thread
```json
{
  "id": "_id.$oid",
  "properties": ["title", "created_at", "comment_count"],
  "relations": ["belongsToCourse", "hasComments"]
}
```

### Relaciones

| Relación | Origen | Destino | Descripción |
|----------|--------|---------|-------------|
| `postedComment` | Author | Comment | Autor publicó comentario |
| `startedThread` | Author | Thread | Autor inició hilo |
| `aboutCourse` | Comment | Course | Comentario sobre curso |
| `inThread` | Comment | Thread | Comentario en hilo |
| `replyTo` | Comment | Comment | Respuesta a comentario |
| `belongsToCourse` | Thread | Course | Hilo pertenece a curso |
| `hasComments` | Thread | Comment | Hilo tiene comentarios |

## Análisis de Datos

### Métricas de Calidad

```python
def analyze_data_quality(self) -> Dict:
    stats = {
        'total_records': len(self.df),
        'comments': self.df['is_comment'].sum(),
        'threads': self.df['is_thread'].sum(),
        'missing_body': self.df['body'].isna().sum(),
        'missing_author': self.df['author_username'].isna().sum(),
        'missing_course': self.df['course_id'].isna().sum(),
        'date_range': (self.df['created_at'].min(), self.df['created_at'].max()),
        'unique_authors': self.df['author_username'].nunique(),
        'unique_courses': self.df['course_id'].nunique(),
        'avg_text_length': self.df['text_length'].mean(),
        'avg_word_count': self.df['word_count'].mean(),
        'avg_votes': self.df['votes_total'].mean()
    }
```

### Estadísticas del Dataset

- **Total de registros**: 182,500
- **Comentarios**: 117,906 (64.6%)
- **Hilos de discusión**: 64,594 (35.4%)
- **Autores únicos**: 49,633
- **Cursos únicos**: 455
- **Longitud promedio de texto**: 248 caracteres
- **Palabras promedio por comentario**: 41.3
- **Votos promedio**: 0.08
- **Comentarios que son respuestas**: 25,104 (13.8%)

### Distribución de Actividad

**Top 10 Autores Más Activos:**
1. LeninCamacho: 2,407 comentarios
2. mariadelcisne: 1,786 comentarios
3. mrramirez: 1,564 comentarios
4. DianaEspinoza: 880 comentarios
5. dhduncan: 660 comentarios

**Top 10 Cursos con Más Comentarios:**
1. course-v1:UTPL+GPSY3+2020_1: 8,889 comentarios
2. course-v1:UTPL+PRESCHEDU3+2020_1: 6,226 comentarios
3. course-v1:UTPL+ADMINI3+2020_1: 6,050 comentarios
4. course-v1:UTPL+EAIG6+2020_1: 5,460 comentarios
5. course-v1:UTPL+HG13+2020_1: 5,174 comentarios

## Exportación de Datos

### Formato CSV

**Entidades:**
- `courses.csv`: Lista de cursos únicos
- `authors.csv`: Lista de autores únicos
- `comments.csv`: Comentarios procesados con metadatos
- `threads.csv`: Hilos de discusión

**Relaciones:**
- `relations_author_posted_comment.csv`: Relación autor-comentario
- `relations_comment_belongs_to_thread.csv`: Relación comentario-hilo
- `relations_comment_about_course.csv`: Relación comentario-curso
- `relations_reply_to_comment.csv`: Relación respuesta-comentario

### Formato JSON

```json
{
  "entities": {
    "courses": [...],
    "authors": [...],
    "comments": [...],
    "threads": [...]
  },
  "relations": {
    "author_posted_comment": [...],
    "comment_belongs_to_thread": [...],
    "comment_about_course": [...],
    "reply_to_comment": [...]
  }
}
```

## Visualizaciones

### Gráficos Generados

1. **Distribución de Longitud de Texto**
   - Histograma de caracteres por comentario
   - Análisis de patrones de escritura

2. **Distribución de Votos**
   - Top 20 distribución de votos
   - Análisis de engagement

3. **Comentarios por Curso (Top 20)**
   - Gráfico de barras por curso
   - Identificación de cursos más activos

4. **Comentarios por Autor (Top 20)**
   - Gráfico de barras por autor
   - Identificación de usuarios más activos

### Configuración de Visualizaciones

```python
plt.figure(figsize=(15, 10))
plt.subplot(2, 2, 1)  # Distribución de longitud
plt.subplot(2, 2, 2)  # Distribución de votos
plt.subplot(2, 2, 3)  # Comentarios por curso
plt.subplot(2, 2, 4)  # Comentarios por autor
plt.tight_layout()
```

## Consideraciones Técnicas

### Rendimiento

- **Manejo de memoria**: Procesamiento por lotes para datasets grandes
- **Optimización**: Uso de pandas para operaciones vectorizadas
- **Progreso**: Barra de progreso con tqdm para operaciones largas

### Robustez

- **Manejo de errores**: Try-catch para operaciones críticas
- **Validación de datos**: Verificación de tipos y formatos
- **Datos faltantes**: Manejo graceful de valores NaN

### Escalabilidad

- **Muestreo**: Opción de procesar subconjuntos de datos
- **Modularidad**: Clase reutilizable para diferentes datasets
- **Configuración**: Parámetros flexibles para diferentes casos de uso

### Limitaciones

- **Formato JSON**: Requiere estructura específica de MongoDB
- **Memoria**: Procesamiento completo en memoria
- **Idioma**: Optimizado para texto en español/inglés

### Mejoras Futuras

1. **Procesamiento distribuido**: Apache Spark para datasets muy grandes
2. **Análisis de sentimientos**: Integración con modelos de NLP
3. **Extracción de aspectos**: Identificación automática de temas
4. **API REST**: Interfaz web para consultas
5. **Base de datos**: Almacenamiento en Neo4j o similar
