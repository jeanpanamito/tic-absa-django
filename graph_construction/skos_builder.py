#!/usr/bin/env python3
"""
Generador de grafo SKOS (extendido) a partir de JSON de cursos extraídos

Fuentes de datos utilizadas (únicamente):
- data/exports/cursos_extraidos/comentarios_hg.json
- data/exports/cursos_extraidos/comentarios_evolfund.json

Produce:
- data/exports/skos_nodes.csv (ConceptScheme y Concept: CourseBase, CourseEdition, Thread, Comment, Aspect, Polarity)
- data/exports/skos_edges.csv (skos:hasTopConcept, skos:broader, skos:related)
- data/exports/skos_annotations.csv (plantilla de anotaciones topic/polarity)
- data/exports/sample_skos.ttl (TTL con subconjunto)
- data/exports/ontology_aspects.json (Ontología de aspectos en formato ABSA)

Uso:
  python -m src.graph_construction.skos_builder --limit 500
"""

import os
import argparse
import json
import pandas as pd
from urllib.parse import quote

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'data', 'exports')
CURSOS_DIR = os.path.join(EXPORT_DIR, 'cursos_extraidos')
INPUT_HG_JSON = os.path.join(CURSOS_DIR, 'comentarios_hg.json')
INPUT_EVOLFUND_JSON = os.path.join(CURSOS_DIR, 'comentarios_evolfund.json')

BASE = 'http://example.org/tic-absa/'

# --- ONTOLOGÍA DE ASPECTOS EDUCATIVOS ---
# Esta ontología define la estructura semántica de aspectos para ABSA
ONTOLOGIA_ASPECTOS = {
    "General": {
        "descripcion": "Aspecto genérico del curso",
        "padre": None
    },
    "Contenido": {
        "descripcion": "Materiales y recursos del curso",
        "padre": None
    },
    "Videos": {
        "descripcion": "Material audiovisual",
        "padre": "Contenido"
    },
    "Evaluacion": {
        "descripcion": "Pruebas, tests y calificaciones",
        "padre": None
    },
    "Retos": {
        "descripcion": "Actividades prácticas evaluadas",
        "padre": "Evaluacion"
    },
    "Tutoria": {
        "descripcion": "Soporte del profesor o comunidad",
        "padre": None
    },
    "Plataforma": {
        "descripcion": "Infraestructura tecnológica",
        "padre": None
    },
    "Actividades": {
        "descripcion": "Actividades y tareas del curso",
        "padre": None
    },
    "Foros": {
        "descripcion": "Espacios de discusión",
        "padre": "Actividades"
    }
}

# --- RELACIONES SEMÁNTICAS ENTRE ASPECTOS ---
# Estas relaciones enriquecen el grafo con conexiones no jerárquicas
RELACIONES_ASPECTOS = [
    ("Contenido", "relacionado_con", "Evaluacion"),
    ("Videos", "es_parte_de", "Contenido"),
    ("Retos", "es_parte_de", "Evaluacion"),
    ("Foros", "es_parte_de", "Actividades"),
    ("Tutoria", "ayuda_en", "Evaluacion"),
    ("Plataforma", "soporta", "Contenido"),
    ("Contenido", "usa", "Videos"),
    ("Evaluacion", "incluye", "Retos"),
    ("Plataforma", "soporta", "Actividades"),
    ("Actividades", "incluye", "Foros")
]

# --- CONCEPTOS DE POLARIDAD ---
POLARIDADES = {
    "Positivo": "Sentimiento positivo hacia el aspecto",
    "Negativo": "Sentimiento negativo hacia el aspecto",
    "Neutral": "Sentimiento neutro o no expresado"
}


def iri(path: str) -> str:
    return BASE + quote(path, safe='/:#')


def ensure_dirs():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _read_records_from_json(json_path: str) -> pd.DataFrame:
    if not os.path.exists(json_path):
        return pd.DataFrame()
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data.get('records', [])
    return pd.DataFrame.from_records(records)


def load_ontology_from_json(json_path: str = None) -> dict:
    """
    Carga la ontología de aspectos desde el archivo JSON exportado.
    
    Args:
        json_path: Ruta al archivo JSON de ontología. Si es None, usa la ruta por defecto.
        
    Returns:
        Diccionario con la ontología de aspectos, relaciones y polaridades.
        
    Ejemplo:
        >>> ontology = load_ontology_from_json()
        >>> aspects = ontology['ontologia_aspectos']
        >>> relations = ontology['relaciones_aspectos']
        >>> polarities = ontology['polaridades']
    """
    if json_path is None:
        json_path = os.path.join(EXPORT_DIR, 'ontology_aspects.json')
    
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de ontología: {json_path}\n"
            f"Ejecuta primero: python -m src.graph_construction.skos_builder"
        )
    
    with open(json_path, 'r', encoding='utf-8') as f:
        ontology = json.load(f)
    
    return ontology


def build_skos(limit: int = 500) -> None:
    ensure_dirs()
    # Cargar únicamente los JSON requeridos
    df_hg = _read_records_from_json(INPUT_HG_JSON)
    df_ev = _read_records_from_json(INPUT_EVOLFUND_JSON)
    df_full = pd.concat([df_hg, df_ev], ignore_index=True, sort=False)
    if df_full.empty:
        raise FileNotFoundError("No se encontraron datos en los JSON de cursos extraídos.")

    # Normalizar columnas esperadas
    expected_cols = ['base_course', 'course_id', 'thread_id', 'thread_title', 'comment_id', 'text', 'word_count', 'votes', 'parent_id']
    for col in expected_cols:
        if col not in df_full.columns:
            df_full[col] = pd.NA

    # Limitar por cantidad de comentarios si aplica
    df_subset = df_full
    if limit and len(df_full) > limit:
        # Mantener consistencia de jerarquías (threads/ediciones) dentro del subset
        df_subset = df_full.head(limit)

    # Nodos
    nodes = []
    edges = []

    # ConceptSchemes (según modelo)
    scheme_course_base = iri('scheme/courseBase')
    scheme_course_edition = iri('scheme/courseEdition')
    scheme_thread = iri('scheme/thread')
    scheme_comment = iri('scheme/comment')
    scheme_aspect = iri('scheme/aspect')
    scheme_polarity = iri('scheme/polarity')

    # Declarar ConceptSchemes como nodos
    schemes = [
        {'id': scheme_course_base, 'type': 'skos:ConceptScheme', 'prefLabel': 'Course Base', 'definition': 'Agrupa los cursos base (p.ej., EVOLFUND, HG).'},
        {'id': scheme_course_edition, 'type': 'skos:ConceptScheme', 'prefLabel': 'Course Edition', 'definition': 'Agrupa ediciones de cursos (course_id).'},
        {'id': scheme_thread, 'type': 'skos:ConceptScheme', 'prefLabel': 'Thread', 'definition': 'Agrupa hilos de discusión.'},
        {'id': scheme_comment, 'type': 'skos:ConceptScheme', 'prefLabel': 'Comment', 'definition': 'Agrupa comentarios en foros.'},
        {'id': scheme_aspect, 'type': 'skos:ConceptScheme', 'prefLabel': 'Aspectos', 'definition': 'Esquema de conceptos para tópicos (aspectos) de anotación.'},
        {'id': scheme_polarity, 'type': 'skos:ConceptScheme', 'prefLabel': 'Polaridad', 'definition': 'Esquema de conceptos para polaridades de anotación.'},
    ]
    nodes.extend(schemes)

    # CourseBase (Concepts)
    for base in df_full['base_course'].dropna().astype(str).unique().tolist():
        cb_id = iri(f'courseBase/{base}')
        nodes.append({
            'id': cb_id,
            'type': 'skos:Concept',
            'prefLabel': base,
            'inScheme': scheme_course_base
        })
        edges.append({'from': scheme_course_base, 'prop': 'skos:hasTopConcept', 'to': cb_id})

    # CourseEdition (Concepts) y jerarquía con CourseBase
    for cid, base in (
        df_full[['course_id', 'base_course']]
        .dropna(subset=['course_id'])
        .astype({'course_id': str})
        .drop_duplicates()
        .itertuples(index=False)
    ):
        ce_id = iri(f'courseEdition/{cid}')
        nodes.append({
            'id': ce_id,
            'type': 'skos:Concept',
            'prefLabel': cid,
            'inScheme': scheme_course_edition
        })
        edges.append({'from': scheme_course_edition, 'prop': 'skos:hasTopConcept', 'to': ce_id})
        if pd.notna(base):
            edges.append({'from': ce_id, 'prop': 'skos:broader', 'to': iri(f'courseBase/{base}')})

    # Threads (Concepts) y jerarquía con CourseEdition
    for tid, ttitle, cid in (
        df_subset[['thread_id', 'thread_title', 'course_id']]
        .dropna(subset=['thread_id'])
        .astype({'thread_id': str})
        .drop_duplicates()
        .itertuples(index=False)
    ):
        t_id = iri(f'thread/{tid}')
        nodes.append({
            'id': t_id,
            'type': 'skos:Concept',
            'prefLabel': str(ttitle) if pd.notna(ttitle) else f'Thread {tid}',
            'inScheme': scheme_thread
        })
        edges.append({'from': scheme_thread, 'prop': 'skos:hasTopConcept', 'to': t_id})
        if pd.notna(cid):
            edges.append({'from': t_id, 'prop': 'skos:broader', 'to': iri(f'courseEdition/{cid}')})

    # Comments (Concepts) y relaciones replyTo
    df_local = (
        df_subset[['comment_id', 'text', 'thread_id', 'course_id', 'parent_id']]
        .dropna(subset=['comment_id'])
        .astype({'comment_id': str})
        .drop_duplicates(subset=['comment_id'])
    )
    present_comments = set(df_local['comment_id'].astype(str))

    for _, r in df_local.iterrows():
        com_id = str(r['comment_id'])
        nodes.append({
            'id': iri(f'comment/{com_id}'),
            'type': 'skos:Concept',
            'prefLabel': f'Comment {com_id}',
            'note': str(r.get('text', '')),
            'inScheme': scheme_comment
        })
        # Jerarquía: Comment -> Thread
        if pd.notna(r['thread_id']):
            edges.append({'from': iri(f'comment/{com_id}'), 'prop': 'skos:broader', 'to': iri(f'thread/{str(r["thread_id"])}')})
        # replyTo (skos:related)
        parent = r.get('parent_id')
        if pd.notna(parent):
            pid = str(parent)
            if pid in present_comments:
                edges.append({'from': iri(f'comment/{com_id}'), 'prop': 'skos:related', 'to': iri(f'comment/{pid}')})

    # Aspectos (Concepts) y jerarquía
    # Construir conjunto de relaciones jerárquicas para evitar duplicados en relaciones semánticas
    existing_broader = set()
    
    for aspecto, info in ONTOLOGIA_ASPECTOS.items():
        aspect_id = iri(f'aspect/{aspecto}')
        nodes.append({
            'id': aspect_id,
            'type': 'skos:Concept',
            'prefLabel': aspecto,
            'definition': info['descripcion'],
            'inScheme': scheme_aspect
        })
        edges.append({'from': scheme_aspect, 'prop': 'skos:hasTopConcept', 'to': aspect_id})
        
        # Relación jerárquica con padre (skos:broader)
        if info['padre']:
            parent_id = iri(f'aspect/{info["padre"]}')
            edges.append({'from': aspect_id, 'prop': 'skos:broader', 'to': parent_id})
            # Registrar esta relación jerárquica para evitar duplicados
            existing_broader.add((aspect_id, parent_id))
            existing_broader.add((parent_id, aspect_id))  # Bidireccional para verificación

    # Relaciones semánticas entre aspectos (skos:related)
    
    for sujeto, predicado, objeto in RELACIONES_ASPECTOS:
        sujeto_id = iri(f'aspect/{sujeto}')
        objeto_id = iri(f'aspect/{objeto}')
        # Verificar que ambos aspectos existen en la ontología
        if sujeto in ONTOLOGIA_ASPECTOS and objeto in ONTOLOGIA_ASPECTOS:
            # Evitar agregar skos:related si ya existe una relación jerárquica (broader)
            if (sujeto_id, objeto_id) not in existing_broader and (objeto_id, sujeto_id) not in existing_broader:
                # Usamos skos:related para relaciones semánticas no jerárquicas
                # Nota: SKOS no tiene propiedades personalizadas, así que usamos related
                edges.append({'from': sujeto_id, 'prop': 'skos:related', 'to': objeto_id})

    # Polaridades (Concepts)
    for polaridad, descripcion in POLARIDADES.items():
        polarity_id = iri(f'polarity/{polaridad}')
        nodes.append({
            'id': polarity_id,
            'type': 'skos:Concept',
            'prefLabel': polaridad,
            'definition': descripcion,
            'inScheme': scheme_polarity
        })
        edges.append({'from': scheme_polarity, 'prop': 'skos:hasTopConcept', 'to': polarity_id})

    # Exportar CSV
    nodes_df = pd.DataFrame(nodes).drop_duplicates(subset=['id'])
    edges_df = pd.DataFrame(edges).drop_duplicates()
    nodes_df.to_csv(os.path.join(EXPORT_DIR, 'skos_nodes.csv'), index=False)
    edges_df.to_csv(os.path.join(EXPORT_DIR, 'skos_edges.csv'), index=False)

    # Exportar plantilla de anotaciones (sin datos por ahora)
    annotations_df = pd.DataFrame(columns=[
        'id_anotacion', 'comment_id', 'texto_seleccionado', 'topic_concept_id', 'polarity_concept_id'
    ])
    annotations_df.to_csv(os.path.join(EXPORT_DIR, 'skos_annotations.csv'), index=False)

    # Exportar ontología de aspectos en formato JSON para ABSA
    ontology_for_absa = {
        "ontologia_aspectos": ONTOLOGIA_ASPECTOS,
        "relaciones_aspectos": RELACIONES_ASPECTOS,
        "polaridades": POLARIDADES,
        "metadata": {
            "version": "1.0",
            "descripcion": "Ontología de aspectos educativos para análisis ABSA",
            "formato": "JSON para uso en pipeline ABSA con embeddings y Node2Vec"
        }
    }
    with open(os.path.join(EXPORT_DIR, 'ontology_aspects.json'), 'w', encoding='utf-8') as f:
        json.dump(ontology_for_absa, f, ensure_ascii=False, indent=2)

    # Exportar TTL
    ttl_lines = []
    ttl_lines.append('@prefix skos: <http://www.w3.org/2004/02/skos/core#> .')
    ttl_lines.append('@prefix schema: <http://schema.org/> .')
    ttl_lines.append('@prefix prov: <http://www.w3.org/ns/prov#> .')
    ttl_lines.append(f'@base <{BASE}> .\n')

    for _, n in nodes_df.iterrows():
        ttl_lines.append(f'<{n["id"]}> a {n.get("type","skos:Concept")} ;')
        if pd.notna(n.get('prefLabel')):
            ttl_lines.append(f'  skos:prefLabel """{str(n["prefLabel"]).replace("\"","'")}""" ;')
        if 'definition' in n and pd.notna(n.get('definition')) and str(n['definition']).strip():
            ttl_lines.append(f'  skos:definition """{str(n["definition"]).replace("\"","'")}""" ;')
        if 'note' in n and pd.notna(n.get('note')) and str(n['note']).strip():
            ttl_lines.append(f'  skos:note """{str(n["note"]).replace("\"","'")}""" ;')
        if pd.notna(n.get('inScheme')):
            ttl_lines.append(f'  skos:inScheme <{n["inScheme"]}> ;')
        ttl_lines[-1] = ttl_lines[-1].rstrip(' ;') + ' .'

    for _, e in edges_df.iterrows():
        ttl_lines.append(f'<{e["from"]}> {e["prop"]} <{e["to"]}> .')

    with open(os.path.join(EXPORT_DIR, 'sample_skos.ttl'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(ttl_lines))

    print(f"SKOS export:")
    print(f"- Nodes: {len(nodes_df):,} -> data/exports/skos_nodes.csv")
    print(f"- Edges: {len(edges_df):,} -> data/exports/skos_edges.csv")
    print(f"- Annotations (template): data/exports/skos_annotations.csv")
    print(f"- TTL: data/exports/sample_skos.ttl")
    print(f"- Ontology (ABSA format): data/exports/ontology_aspects.json")
    print(f"\nOntologia de aspectos:")
    print(f"  - Aspectos: {len(ONTOLOGIA_ASPECTOS)}")
    print(f"  - Relaciones: {len(RELACIONES_ASPECTOS)}")
    print(f"  - Polaridades: {len(POLARIDADES)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=500, help='Límite de filas a exportar')
    args = parser.parse_args()
    build_skos(limit=args.limit)


if __name__ == '__main__':
    main()
