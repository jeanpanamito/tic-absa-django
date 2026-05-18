#!/usr/bin/env python3
"""
Generador de tripletas TTL para enriquecer el grafo SKOS con resultados ABSA.

Este script lee los resultados del pipeline ABSA (resultados_absa_completo.json)
y genera tripletas TTL que conectan:
- Comment -> Aspect (relación de anotación)
- Comment -> Polarity (sentimiento detectado)
- Nodos de anotación intermedios con metadatos (confianza, similitud, mencion, justificacion)

Las tripletas generadas son compatibles con GraphDB y enriquecen el grafo SKOS
generado por skos_builder.py.

Uso:
  python -m src.graph_construction.absa_enrichment --input data/exports/resultados_absa_completo.json
"""

import os
import argparse
import json
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'data', 'exports')

BASE = 'http://example.org/tic-absa/'
ABSA_NS = 'http://example.org/tic-absa/absa#'

def iri(path: str) -> str:
    """Genera un IRI completo usando la base URI."""
    return BASE + quote(path, safe='/:#')

def absa_prop(prop: str) -> str:
    """Genera un IRI para una propiedad del namespace ABSA."""
    return ABSA_NS + prop

def escape_ttl_string(text: str) -> str:
    """Escapa caracteres especiales para strings en TTL."""
    if not text:
        return '""'
    # Reemplazar comillas dobles y triples
    text = str(text).replace('"""', '\\"\\"\\"')
    text = text.replace('"', '\\"')
    # Reemplazar saltos de línea
    text = text.replace('\n', '\\n').replace('\r', '\\r')
    return f'"""{text}"""'

def generar_ttl_absa(resultados: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Genera tripletas TTL a partir de los resultados ABSA.
    
    Estructura de relaciones generadas:
    - comment/{id} absa:hasAnnotation annotation/{id_comentario}_{aspecto}_{sentimiento}
    - annotation/{id} absa:hasAspect aspect/{aspecto}
    - annotation/{id} absa:hasPolarity polarity/{sentimiento}
    - annotation/{id} absa:confidence {confianza}
    - annotation/{id} absa:similarity {similitud}
    - annotation/{id} absa:mention {mencion}
    - annotation/{id} absa:justification {justificacion}
    """
    ttl_lines = []
    
    # Prefijos
    ttl_lines.append('@prefix skos: <http://www.w3.org/2004/02/skos/core#> .')
    ttl_lines.append('@prefix schema: <http://schema.org/> .')
    ttl_lines.append('@prefix prov: <http://www.w3.org/ns/prov#> .')
    ttl_lines.append(f'@prefix absa: <{ABSA_NS}> .')
    ttl_lines.append(f'@base <{BASE}> .\n')
    
    # Contadores para estadísticas
    total_anotaciones = 0
    comentarios_con_anotaciones = set()
    aspectos_anotados = set()
    polaridades_anotadas = set()
    
    # Generar tripletas para cada resultado ABSA
    for idx, resultado in enumerate(resultados):
        comment_id = resultado.get('id_comentario')
        aspecto = resultado.get('aspecto')
        sentimiento = resultado.get('sentimiento')
        
        if not comment_id or not aspecto or not sentimiento:
            continue
        
        # ID único para la anotación (combinando comentario, aspecto y sentimiento)
        # Usamos un hash simple basado en el índice para evitar IDs muy largos
        annotation_id = f"annotation/{comment_id}_{aspecto}_{sentimiento}_{idx}"
        annotation_iri = iri(annotation_id)
        comment_iri = iri(f'comment/{comment_id}')
        aspect_iri = iri(f'aspect/{aspecto}')
        polarity_iri = iri(f'polarity/{sentimiento}')
        
        # Triple: Comment -> Annotation
        ttl_lines.append(f'<{comment_iri}> absa:hasAnnotation <{annotation_iri}> .')
        
        # Triple: Annotation es una instancia de absa:Annotation
        ttl_lines.append(f'<{annotation_iri}> a absa:Annotation .')
        
        # Triple: Annotation -> Aspect
        ttl_lines.append(f'<{annotation_iri}> absa:hasAspect <{aspect_iri}> .')
        
        # Triple: Annotation -> Polarity
        ttl_lines.append(f'<{annotation_iri}> absa:hasPolarity <{polarity_iri}> .')
        
        # Metadatos de la anotación
        confianza = resultado.get('confianza')
        if confianza is not None:
            ttl_lines.append(f'<{annotation_iri}> absa:confidence {float(confianza):.4f} .')
        
        similitud = resultado.get('similitud_embedding')
        if similitud is not None:
            ttl_lines.append(f'<{annotation_iri}> absa:similarity {float(similitud):.6f} .')
        
        mencion = resultado.get('mencion')
        if mencion:
            ttl_lines.append(f'<{annotation_iri}> absa:mention {escape_ttl_string(mencion)} .')
        
        justificacion = resultado.get('justificacion')
        if justificacion:
            ttl_lines.append(f'<{annotation_iri}> absa:justification {escape_ttl_string(justificacion)} .')
        
        # Metadatos adicionales opcionales
        embedding_dim = resultado.get('embedding_dimension')
        if embedding_dim:
            ttl_lines.append(f'<{annotation_iri}> absa:embeddingDimension {int(embedding_dim)} .')
        
        # Relaciones opcionales con course_id, base_course, thread_id si existen
        course_id = resultado.get('course_id')
        if course_id:
            course_iri = iri(f'courseEdition/{course_id}')
            ttl_lines.append(f'<{annotation_iri}> absa:inCourse <{course_iri}> .')
        
        base_course = resultado.get('base_course')
        if base_course:
            base_iri = iri(f'courseBase/{base_course}')
            ttl_lines.append(f'<{annotation_iri}> absa:inBaseCourse <{base_iri}> .')
        
        thread_id = resultado.get('thread_id')
        if thread_id:
            thread_iri = iri(f'thread/{thread_id}')
            ttl_lines.append(f'<{annotation_iri}> absa:inThread <{thread_iri}> .')
        
        ttl_lines.append('')  # Línea en blanco para legibilidad
        
        # Actualizar estadísticas
        total_anotaciones += 1
        comentarios_con_anotaciones.add(comment_id)
        aspectos_anotados.add(aspecto)
        polaridades_anotadas.add(sentimiento)
    
    # Escribir archivo TTL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ttl_lines))
    
    # Imprimir estadísticas
    print(f"\n{'=' * 80}")
    print("GENERACIÓN DE TRIPLETAS TTL PARA ENRIQUECIMIENTO ABSA")
    print(f"{'=' * 80}")
    print(f"\n[OK] Archivo generado: {output_path.as_posix()}")
    print(f"\nEstadísticas:")
    print(f"  - Total de anotaciones ABSA: {total_anotaciones:,}")
    print(f"  - Comentarios con anotaciones: {len(comentarios_con_anotaciones):,}")
    print(f"  - Aspectos anotados: {len(aspectos_anotados)}")
    print(f"    {', '.join(sorted(aspectos_anotados))}")
    print(f"  - Polaridades detectadas: {len(polaridades_anotadas)}")
    print(f"    {', '.join(sorted(polaridades_anotadas))}")
    print(f"\nRelaciones generadas:")
    print(f"  - absa:hasAnnotation (Comment -> Annotation): {total_anotaciones:,}")
    print(f"  - absa:hasAspect (Annotation -> Aspect): {total_anotaciones:,}")
    print(f"  - absa:hasPolarity (Annotation -> Polarity): {total_anotaciones:,}")
    print(f"\n{'=' * 80}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Genera tripletas TTL para enriquecer el grafo SKOS con resultados ABSA."
    )
    parser.add_argument(
        '--input',
        type=str,
        default=str(Path(EXPORT_DIR) / 'resultados_absa_completo.json'),
        help='Ruta al archivo JSON con resultados ABSA'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=str(Path(EXPORT_DIR) / 'absa_enrichment.ttl'),
        help='Ruta de salida para el archivo TTL'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Límite de resultados a procesar (útil para pruebas)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de resultados ABSA: {input_path}\n"
            f"Ejecuta primero el pipeline ABSA: python -m src.absa.semantic_pipeline"
        )
    
    print(f"Cargando resultados ABSA desde: {input_path.as_posix()}")
    with open(input_path, 'r', encoding='utf-8') as f:
        resultados = json.load(f)
    
    if args.limit:
        resultados = resultados[:args.limit]
        print(f"Procesando solo los primeros {args.limit} resultados (modo prueba)")
    
    output_path = Path(args.output)
    generar_ttl_absa(resultados, output_path)

if __name__ == '__main__':
    main()

