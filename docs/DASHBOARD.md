# Dashboard TIC ABSA Knowledge Graph

Dashboard interactivo desarrollado con Streamlit para visualizar y analizar el grafo de conocimiento TIC ABSA.

## Características

- 📊 **Estadísticas Generales**: Resumen de anotaciones, comentarios, confianza promedio, etc.
- 📈 **Análisis Detallado**: Gráficos de distribución, heatmaps de aspectos vs polaridades
- 🕸️ **Visualización de Grafos**: Visualización interactiva de nodos y relaciones
- 🔍 **Consultas SPARQL**: Ejecución de queries personalizadas sobre GraphDB o archivos locales

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Asegúrate de tener los archivos de datos en `data/exports/`:
   - `resultados_absa_completo.json` o `resultados_absa_prueba.json`
   - `absa_enrichment.ttl` (opcional, para carga desde TTL)
   - `sample_skos.ttl` (opcional, para carga desde TTL)

## Uso

### Ejecutar el Dashboard

```bash
python run_dashboard.py
```

O directamente con Streamlit:

```bash
streamlit run src/dashboard/dashboard.py
```

El dashboard se abrirá en `http://localhost:8501`

### Configuración de Fuentes de Datos

El dashboard soporta tres fuentes de datos:

#### 1. Archivos Locales (TTL)
- Carga archivos TTL desde `data/exports/`
- Soporta múltiples archivos TTL
- Útil para análisis local sin GraphDB

#### 2. GraphDB Endpoint
- Conecta a un servidor GraphDB remoto o local
- Requiere:
  - URL del endpoint (ej: `http://localhost:7200`)
  - Nombre del repositorio (ej: `tic-absa`)
- Permite ejecutar queries SPARQL directamente sobre GraphDB

#### 3. Archivo JSON ABSA
- Carga resultados del pipeline ABSA desde JSON
- Permite análisis estadístico rápido
- No requiere GraphDB ni archivos TTL

## Secciones del Dashboard

### 📈 Overview
- Métricas principales (total anotaciones, comentarios, confianza promedio)
- Gráficos de distribución de polaridades
- Gráficos de barras de aspectos

### 📊 Estadísticas
- Filtros interactivos por aspecto, polaridad y confianza
- Heatmap de aspectos vs polaridades
- Distribución de confianza
- Tabla de datos filtrados

### 🕸️ Visualización de Grafos
- Grafo interactivo con nodos y relaciones
- Configuración de número máximo de nodos
- Visualización con pyvis (HTML interactivo)
- Colores diferenciados por tipo de nodo:
  - Azul: Comentarios
  - Verde: Aspectos
  - Rojo/Verde/Gris: Polaridades (Negativo/Positivo/Neutral)

### 🔍 SPARQL Queries
- Queries predefinidas:
  - Distribución de sentimientos por aspecto
  - Top comentarios con alta confianza
  - Aspectos más problemáticos
- Editor de queries personalizadas
- Exportación de resultados a CSV

## Queries SPARQL Predefinidas

### Distribución de Sentimientos por Aspecto
Muestra la cantidad de anotaciones agrupadas por aspecto y polaridad, con confianza promedio.

### Top Comentarios con Alta Confianza
Lista los comentarios con confianza >= 0.8, ordenados por confianza descendente.

### Aspectos más Problemáticos
Identifica aspectos con mayor cantidad de comentarios negativos.

## Estructura del Código

```
src/dashboard/
├── __init__.py
├── dashboard.py          # Dashboard principal Streamlit
└── graphdb_connector.py  # Módulo de conexión a GraphDB y carga TTL
```

## Dependencias Principales

- `streamlit`: Framework del dashboard
- `plotly`: Gráficos interactivos
- `networkx`: Construcción de grafos
- `pyvis`: Visualización de grafos interactivos
- `pandas`: Manipulación de datos
- `rdflib`: Procesamiento RDF/SPARQL
- `SPARQLWrapper`: Conexión a endpoints SPARQL

## Troubleshooting

### Error: "SPARQLWrapper no está instalado"
```bash
pip install SPARQLWrapper
```

### Error: "No se encuentran archivos TTL"
- Verifica que los archivos estén en `data/exports/`
- Usa la opción "Archivo JSON ABSA" como alternativa

### Error de conexión a GraphDB
- Verifica que GraphDB esté corriendo
- Verifica la URL del endpoint y nombre del repositorio
- Asegúrate de que el repositorio exista en GraphDB

### El grafo no se visualiza
- Reduce el número máximo de nodos
- Verifica que haya datos cargados
- Revisa la consola del navegador para errores JavaScript

## Próximas Mejoras

- [ ] Caché de queries SPARQL para mejor rendimiento
- [ ] Exportación de visualizaciones del grafo
- [ ] Filtros avanzados en la visualización del grafo
- [ ] Análisis temporal de sentimientos
- [ ] Comparación entre cursos/ediciones
- [ ] Integración con más fuentes de datos

## Autor

Jean Panamito - jppanamito@utpl.edu.ec

