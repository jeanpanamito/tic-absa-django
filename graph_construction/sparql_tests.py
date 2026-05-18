#!/usr/bin/env python3
"""
Pruebas SPARQL sobre los TTL generados:
- Carga: data/exports/sample_skos.ttl (y opcionalmente aspect_sample.ttl)
- Ejecuta consultas de ejemplo y muestra resultados.

Uso:
  python -m src.graph_construction.sparql_tests
"""

import os
import csv
from rdflib import Graph

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'data', 'exports')
TTL_SKOS = os.path.join(EXPORT_DIR, 'sample_skos.ttl')
TTL_ABSA = os.path.join(EXPORT_DIR, 'aspect_sample.ttl')


def load_graph() -> Graph:
    g = Graph()
    if os.path.exists(TTL_SKOS):
        g.parse(TTL_SKOS, format='turtle')
    if os.path.exists(TTL_ABSA):
        g.parse(TTL_ABSA, format='turtle')
    return g


BASE = 'http://example.org/tic-absa/'


def _short_id(uri: str) -> str:
    """Devuelve solo el identificador local sin la URL base.
    Ej.: http://example.org/tic-absa/comment/ABC -> ABC
    """
    if uri is None:
        return ''
    s = str(uri)
    if s.startswith(BASE):
        s = s[len(BASE):]
    # remover prefijo de clase (comment/, thread/, course/, author/, aspect/)
    parts = s.split('/')
    return parts[-1] if parts else s


def run_queries(g: Graph, export_spo_csv: bool = False) -> None:
    print('Triples totales:', len(g))

    q_courses = """
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?c WHERE { ?c a skos:Concept ; skos:inScheme <http://example.org/tic-absa/scheme/course> . } LIMIT 10
    """

    q_comments_by_course = """
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX schema: <http://schema.org/>
    SELECT ?comment ?course ?note WHERE {
      ?comment skos:broader ?course ;
               skos:note ?note .
      ?course skos:inScheme <http://example.org/tic-absa/scheme/course> .
    } LIMIT 10
    """

    q_reply = """
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?c1 ?c1_note ?c2 ?c2_note WHERE {
      ?c1 skos:related ?c2 ; skos:note ?c1_note .
      OPTIONAL { ?c2 skos:note ?c2_note }
    } LIMIT 10
    """

    q_about = """
    PREFIX schema: <http://schema.org/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?cmt ?note ?course WHERE {
      ?cmt schema:about ?course ; skos:note ?note .
    } LIMIT 10
    """

    q_author = """
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?cmt ?note ?author WHERE {
      ?cmt prov:wasAttributedTo ?author ; skos:note ?note .
    } LIMIT 10
    """

    q_aspects = """
    PREFIX absa: <http://example.org/absa#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?cmt ?note ?aspect WHERE {
      ?cmt absa:hasAspect ?aspect ; skos:note ?note .
    } LIMIT 10
    """

    q_comment_with_thread_course = """
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?comment ?note ?thread ?course WHERE {
      ?comment skos:note ?note .
      OPTIONAL { ?comment skos:broader ?thread . ?thread skos:inScheme <http://example.org/tic-absa/scheme/thread> }
      OPTIONAL { ?comment skos:broader ?course . ?course skos:inScheme <http://example.org/tic-absa/scheme/course> }
    } LIMIT 10
    """

    results_for_export = []

    for name, q in [
        ('Cursos', q_courses),
        ('Comentarios por curso (con nota)', q_comments_by_course),
        ('Respuestas (replyTo)', q_reply),
        ('About course (con nota)', q_about),
        ('Autoría (con nota)', q_author),
        ('Aspectos (ABSA, con nota)', q_aspects),
        ('Comentario -> hilo/curso (con nota)', q_comment_with_thread_course),
    ]:
        print(f"\n== {name} ==")
        rows = list(g.query(q))
        for row in rows:
            print(tuple(row))

        # Recolectar SPO normalizados para exportación
        if export_spo_csv:
            if name == 'Comentarios por curso (con nota)':
                for (cmt, course, _note) in rows:
                    results_for_export.append((_short_id(cmt), 'skos:broader', _short_id(course)))
            elif name == 'Respuestas (replyTo)':
                for (c1, _n1, c2, _n2) in rows:
                    results_for_export.append((_short_id(c1), 'skos:related', _short_id(c2)))
            elif name == 'About course (con nota)':
                for (cmt, _note, course) in rows:
                    results_for_export.append((_short_id(cmt), 'schema:about', _short_id(course)))
            elif name == 'Autoría (con nota)':
                for (cmt, _note, author) in rows:
                    results_for_export.append((_short_id(cmt), 'prov:wasAttributedTo', _short_id(author)))
            elif name == 'Aspectos (ABSA, con nota)':
                for (cmt, _note, aspect) in rows:
                    results_for_export.append((_short_id(cmt), 'absa:hasAspect', _short_id(aspect)))
            elif name == 'Comentario -> hilo/curso (con nota)':
                for (cmt, _note, thread, course) in rows:
                    if thread is not None:
                        results_for_export.append((_short_id(cmt), 'skos:broader', _short_id(thread)))
                    if course is not None:
                        results_for_export.append((_short_id(cmt), 'skos:broader', _short_id(course)))

    if export_spo_csv and results_for_export:
        out_path = os.path.join(EXPORT_DIR, 'sparql_spo.csv')
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['subject', 'predicate', 'object'])
            # eliminar duplicados preservando orden
            seen = set()
            for triple in results_for_export:
                if triple not in seen:
                    w.writerow(triple)
                    seen.add(triple)
        print(f"\nSPO exportado a CSV (sin URLs): {out_path}")


def main() -> None:
    g = load_graph()
    run_queries(g, export_spo_csv=True)


if __name__ == '__main__':
    main()
