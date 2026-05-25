# TIC ABSA Knowledge Graph Dashboard

Dashboard analítico web para el sistema de Análisis de Sentimientos Basado en Aspectos (ABSA) sobre comentarios de estudiantes universitarios.

## Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| **Backend** | Django 4.2, Python 3.10+ |
| **Base de Datos Analítica** | Neo4j (grafo SKOS con modelo ABSA) |
| **RAG** | LlamaIndex + OpenAI (GPT-4o-mini, text-embedding-3-small) |
| **Frontend** | Tailwind CSS v3, Plotly.js, Vis.js |
| **Interactividad** | Fetch API (AJAX) — sin recargas de página |

## Arquitectura

```
tic-absa-django/
├── manage.py
├── tic_absa_project/        # Django config (settings, urls)
├── analytics/               # App principal
│   ├── services/            # Capa de servicios (Neo4j + RAG)
│   ├── views.py             # Template views (4 páginas)
│   ├── api_views.py         # JSON API endpoints
│   ├── templates/           # HTML (Tailwind + Plotly.js + Vis.js)
│   └── static/              # CSS + JS
└── requirements.txt
```

## Instalación

```bash
# 1. Clonar
git clone https://github.com/tu-usuario/tic-absa-django.git
cd tic-absa-django

# 2. Entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env
# Editar .env con tus credenciales de Neo4j y OpenAI

# 5. Migraciones Django
python manage.py migrate

# 6. Ejecutar
python manage.py runserver
```

Abre `http://localhost:8000` en tu navegador.

## Requisitos Previos

- **Neo4j** corriendo con el grafo ABSA cargado (nodos: Comment, Aspect, Thread, CourseEdition, CourseBase)
- **OpenAI API Key** válida (para funciones RAG)
- **Python 3.10+**

## Páginas

| Ruta | Descripción |
|------|-------------|
| `/` | Overview — KPIs, distribuciones de polaridad y aspectos, heatmap |
| `/detailed/` | Análisis — Top quejas, ranking cursos, confianza, explorador de datos |
| `/graph/` | Grafo — Visualización Vis.js interactiva de la red Comentario → Aspecto |
| `/rag/` | RAG — Chat inteligente con búsqueda híbrida + reportes ejecutivos |

## Autor

Jean Panamito — jppanamito@utpl.edu.ec

## Experiments

This project includes a comprehensive experiment layer inside the `evaluation/` directory to fulfill Phase 5 (Evaluation) of the Design Science Research (DSR) methodology (Peffers et al., 2007). It addresses two main research questions:
1. **RQ1**: How do hybrid ABSA pipelines compare against purely vector-based and purely majority-class baselines?
2. **RQ2**: How do different LLMs (GPT-4o-mini, GPT-4o, Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 2.5 Pro) compare in terms of sentiment F1 score, aspect accuracy, latency, and cost when using identical prompts?

To run the experiments, configure `.env` with your API keys and run:
```bash
python -m evaluation.run_all_experiments
```
Use `python -m evaluation.run_all_experiments --help` for options like `--dry-run` or running specific subsets.

## Licencia

MIT
