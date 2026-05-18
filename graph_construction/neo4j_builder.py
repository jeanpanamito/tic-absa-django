#!/usr/bin/env python3
"""
Generador de export para Neo4j a partir del mismo modelo del skos_builder.

Fuentes de datos utilizadas (únicamente):
- data/exports/cursos_extraidos/comentarios_hg.json
- data/exports/cursos_extraidos/comentarios_evolfund.json

Produce (en data/exports):
- neo4j_nodes.csv      (formato Bulk Import: :ID, :LABEL, propiedades)
- neo4j_rels.csv       (formato Bulk Import: :START_ID, :END_ID, :TYPE)
- neo4j_load.cypher    (script para cargar con LOAD CSV si no se usa bulk)

Uso:
  python -m src.graph_construction.neo4j_builder --limit 500
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

# --- ONTOLOGÍA DE ASPECTOS EDUCATIVOS (idéntica a skos_builder) ---
ONTOLOGIA_ASPECTOS = {
    "General": {"descripcion": "Aspecto genérico del curso", "padre": None},
    "Contenido": {"descripcion": "Materiales y recursos del curso", "padre": None},
    "Videos": {"descripcion": "Material audiovisual", "padre": "Contenido"},
    "Evaluacion": {"descripcion": "Pruebas, tests y calificaciones", "padre": None},
    "Retos": {"descripcion": "Actividades prácticas evaluadas", "padre": "Evaluacion"},
    "Tutoria": {"descripcion": "Soporte del profesor o comunidad", "padre": None},
    "Plataforma": {"descripcion": "Infraestructura tecnológica", "padre": None},
    "Actividades": {"descripcion": "Actividades y tareas del curso", "padre": None},
    "Foros": {"descripcion": "Espacios de discusión", "padre": "Actividades"},
}

# --- RELACIONES SEMÁNTICAS ENTRE ASPECTOS ---
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
    ("Actividades", "incluye", "Foros"),
]

# --- CONCEPTOS DE POLARIDAD ---
POLARIDADES = {
    "Positivo": "Sentimiento positivo hacia el aspecto",
    "Negativo": "Sentimiento negativo hacia el aspecto",
    "Neutral": "Sentimiento neutro o no expresado",
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


def _label_from_scheme(in_scheme: str, fallback: str) -> str:
    """
    Deriva una etiqueta secundaria basada en el scheme para Neo4j.
    Ej: scheme/aspect -> Aspect
    """
    if not in_scheme or not isinstance(in_scheme, str):
        return fallback
    tail = in_scheme.rsplit('/', 1)[-1]
    mapping = {
        'courseBase': 'CourseBase',
        'courseEdition': 'CourseEdition',
        'thread': 'Thread',
        'comment': 'Comment',
        'aspect': 'Aspect',
        'polarity': 'Polarity',
    }
    return mapping.get(tail, fallback)


def _rel_type_from_skos(prop: str) -> str:
    """
    Convierte propiedades SKOS a tipos de relación aptos para Neo4j.
    """
    if prop.endswith('hasTopConcept'):
        return 'HAS_TOP_CONCEPT'
    if prop.endswith('broader'):
        return 'BROADER'
    if prop.endswith('related'):
        return 'RELATED'
    # fallback genérico
    safe = prop.split('/')[-1].upper().replace(':', '_').replace('-', '_')
    return safe or 'RELATED'


def build_neo4j(limit: int = 500) -> None:
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
        df_subset = df_full.head(limit)

    # Construcción de nodos y aristas (reusa la lógica del skos_builder)
    nodes = []
    edges = []

    # ConceptSchemes (para etiquetar)
    scheme_course_base = iri('scheme/courseBase')
    scheme_course_edition = iri('scheme/courseEdition')
    scheme_thread = iri('scheme/thread')
    scheme_comment = iri('scheme/comment')
    scheme_aspect = iri('scheme/aspect')
    scheme_polarity = iri('scheme/polarity')

    # Declarar ConceptSchemes como nodos
    schemes = [
        {'id': scheme_course_base, 'type': 'skos:ConceptScheme', 'prefLabel': 'Course Base'},
        {'id': scheme_course_edition, 'type': 'skos:ConceptScheme', 'prefLabel': 'Course Edition'},
        {'id': scheme_thread, 'type': 'skos:ConceptScheme', 'prefLabel': 'Thread'},
        {'id': scheme_comment, 'type': 'skos:ConceptScheme', 'prefLabel': 'Comment'},
        {'id': scheme_aspect, 'type': 'skos:ConceptScheme', 'prefLabel': 'Aspectos'},
        {'id': scheme_polarity, 'type': 'skos:ConceptScheme', 'prefLabel': 'Polaridad'},
    ]
    nodes.extend(schemes)

    # CourseBase
    for base in df_full['base_course'].dropna().astype(str).unique().tolist():
        cb_id = iri(f'courseBase/{base}')
        nodes.append({
            'id': cb_id,
            'type': 'skos:Concept',
            'prefLabel': base,
            'inScheme': scheme_course_base
        })
        edges.append({'from': scheme_course_base, 'prop': 'skos:hasTopConcept', 'to': cb_id})

    # CourseEdition + broader hacia CourseBase
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

    # Threads
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

    # Comments + replyTo como related
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
        if pd.notna(r['thread_id']):
            edges.append({'from': iri(f'comment/{com_id}'), 'prop': 'skos:broader', 'to': iri(f'thread/{str(r["thread_id"])}')})
        parent = r.get('parent_id')
        if pd.notna(parent):
            pid = str(parent)
            if pid in present_comments:
                edges.append({'from': iri(f'comment/{com_id}'), 'prop': 'skos:related', 'to': iri(f'comment/{pid}')})

    # Aspectos
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
        if info['padre']:
            parent_id = iri(f'aspect/{info["padre"]}')
            edges.append({'from': aspect_id, 'prop': 'skos:broader', 'to': parent_id})
            existing_broader.add((aspect_id, parent_id))
            existing_broader.add((parent_id, aspect_id))

    # Relaciones semánticas entre aspectos (no jerárquicas)
    for sujeto, _, objeto in RELACIONES_ASPECTOS:
        sujeto_id = iri(f'aspect/{sujeto}')
        objeto_id = iri(f'aspect/{objeto}')
        if sujeto in ONTOLOGIA_ASPECTOS and objeto in ONTOLOGIA_ASPECTOS:
            if (sujeto_id, objeto_id) not in existing_broader and (objeto_id, sujeto_id) not in existing_broader:
                edges.append({'from': sujeto_id, 'prop': 'skos:related', 'to': objeto_id})

    # Polaridades
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

    # Deduplicación
    nodes_df = pd.DataFrame(nodes).drop_duplicates(subset=['id'])
    edges_df = pd.DataFrame(edges).drop_duplicates()

    # Preparación para Bulk Import de Neo4j
    # :ID y :LABEL
    def compute_label(row) -> str:
        base_label = 'ConceptScheme' if row.get('type') == 'skos:ConceptScheme' else 'Concept'
        # Agregar una etiqueta específica del esquema (p.ej., Aspect)
        specific = _label_from_scheme(row.get('inScheme'), '')
        if specific and base_label != 'ConceptScheme':
            return f"{base_label};{specific}"
        return base_label

    neo_nodes = pd.DataFrame({
        ':ID': nodes_df['id'],
        ':LABEL': nodes_df.apply(compute_label, axis=1),
        'prefLabel': nodes_df.get('prefLabel', pd.Series([pd.NA]*len(nodes_df))),
        'definition': nodes_df.get('definition', pd.Series([pd.NA]*len(nodes_df))),
        'note': nodes_df.get('note', pd.Series([pd.NA]*len(nodes_df))),
        'inScheme': nodes_df.get('inScheme', pd.Series([pd.NA]*len(nodes_df))),
    })

    neo_rels = pd.DataFrame({
        ':START_ID': edges_df['from'],
        ':END_ID': edges_df['to'],
        ':TYPE': edges_df['prop'].map(_rel_type_from_skos),
    })

    nodes_path = os.path.join(EXPORT_DIR, 'neo4j_nodes.csv')
    rels_path = os.path.join(EXPORT_DIR, 'neo4j_rels.csv')
    neo_nodes.to_csv(nodes_path, index=False, encoding='utf-8')
    neo_rels.to_csv(rels_path, index=False, encoding='utf-8')

    # Script Cypher de carga con LOAD CSV (para carpeta import/)
    cypher_lines = [
        "// Ajusta los nombres de archivo si los renombraste.",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:ConceptScheme) REQUIRE s.id IS UNIQUE;",
        "",
        "// Cargar nodos",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row FIELDTERMINATOR ','",
        "WITH row, split(row[':LABEL'], ';') AS labels",
        "CALL { WITH row RETURN row[':ID'] AS id, row.prefLabel AS prefLabel, row.definition AS definition, row.note AS note, row.inScheme AS inScheme }",
        "CALL apoc.create.node(labels, {id: id, prefLabel: prefLabel, definition: definition, note: note, inScheme: inScheme}) YIELD node",
        "RETURN count(*) AS createdNodes;",
        "",
        "// Cargar relaciones",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_rels.csv' AS row FIELDTERMINATOR ','",
        "MATCH (a {id: row[':START_ID']}), (b {id: row[':END_ID']})",
        "CALL apoc.create.relationship(a, row[':TYPE'], {}, b) YIELD rel",
        "RETURN count(*) AS createdRels;",
        ""
    ]
    with open(os.path.join(EXPORT_DIR, 'neo4j_load.cypher'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(cypher_lines))

    print("Neo4j export:")
    print(f"- Nodes: {len(neo_nodes):,} -> data/exports/neo4j_nodes.csv")
    print(f"- Rels:  {len(neo_rels):,} -> data/exports/neo4j_rels.csv")
    print(f"- Cypher loader: data/exports/neo4j_load.cypher")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=500, help='Límite de filas a exportar')
    args = parser.parse_args()
    build_neo4j(limit=args.limit)


if __name__ == '__main__':
    main()


