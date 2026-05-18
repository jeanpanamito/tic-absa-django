#!/usr/bin/env python3
"""
Script de Ingesta a Neo4j para GraphRAG (Jerárquico).

Este script lee el JSON generado por `semantic_pipeline.py` y puebla una base de datos Neo4j
respetando la jerarquía completa de la ontología SKOS:
1. BaseCourse -> CourseEdition -> Thread -> Comment
2. Aspect Hierarchy (Padre/Hijo)
3. Aspect Relations (Semánticas)
4. Comment -> Aspect (MENTIONS)

Requisitos:
  pip install neo4j python-dotenv
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to sys.path to allow importing config
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: La librería 'neo4j' no está instalada.")
    print("Instala con: pip install neo4j")
    sys.exit(1)

from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

# Intentar cargar desde config si no están en env
try:
    from config import OPENAI_API_KEY as CONFIG_OPENAI_KEY
    from config import NEO4J_URI as CONFIG_NEO4J_URI
    from config import NEO4J_USER as CONFIG_NEO4J_USER
    from config import NEO4J_PASSWORD as CONFIG_NEO4J_PASSWORD
except ImportError:
    CONFIG_OPENAI_KEY = None
    CONFIG_NEO4J_URI = "bolt://localhost:7687"
    CONFIG_NEO4J_USER = "neo4j"
    CONFIG_NEO4J_PASSWORD = "password"

# Configuración Neo4j
NEO4J_URI = os.getenv("NEO4J_URI") or CONFIG_NEO4J_URI
NEO4J_USER = os.getenv("NEO4J_USER") or CONFIG_NEO4J_USER
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") or CONFIG_NEO4J_PASSWORD



# Configuración de Archivos
INPUT_FILE = Path("data/exports/resultados_absa_completo.json")
ONTOLOGY_FILE = Path("data/exports/ontology_aspects.json")

BASE = 'http://example.org/tic-absa/'

def iri(path: str) -> str:
    from urllib.parse import quote
    return BASE + quote(path, safe='/:#')

class Neo4jIngester:
    def __init__(self, uri, user, password):
        # Usar argumentos si existen, sino env, sino config
        final_uri = uri or os.getenv("NEO4J_URI") or CONFIG_NEO4J_URI
        final_user = user or os.getenv("NEO4J_USER") or CONFIG_NEO4J_USER
        final_password = password or os.getenv("NEO4J_PASSWORD") or CONFIG_NEO4J_PASSWORD
        
        self.driver = GraphDatabase.driver(final_uri, auth=(final_user, final_password))
        self.lookup_map = {}

    def load_lookup_map(self, lookup_path: Path):
        """Carga un mapa de comment_id -> {course_id, thread_id} desde un JSON externo"""
        if not lookup_path.exists():
            print(f"Warning: No se encontro archivo lookup {lookup_path}")
            return
        
        print(f"Cargando mapa de cursos/hilos desde {lookup_path}...")
        try:
            with open(lookup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Soporte para estructura raw de SRM (lista en "comentarios")
            if "comentarios" in data:
                items = data["comentarios"]
            elif isinstance(data, list):
                items = data
            else:
                items = []

            count = 0
            for item in items:
                cid = item.get("id")
                course = item.get("course_id")
                thread = item.get("thread_id")
                if cid:
                    self.lookup_map[str(cid)] = {
                        "course_id": str(course) if course else None,
                        "thread_id": str(thread) if thread else None
                    }
                    count += 1
            print(f"Mapa de lookup cargado: {count} entradas.")
        except Exception as e:
            print(f"Error cargando lookup map: {e}")

    def close(self):
        self.driver.close()

    def setup_schema(self):
        """Crea índices y restricciones."""
        print("Configurando esquema en Neo4j...")
        with self.driver.session() as session:
            # Restricciones de Unicidad
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:BaseCourse) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:CourseEdition) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Thread) REQUIRE t.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Comment) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE")
            # session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Aspect) REQUIRE a.id IS UNIQUE") # Redundante si tiene etiqueta Concept

    def create_vector_index(self, dimension: int):
        print(f"Creando índice vectorial 'comment_embedding' con dimensión {dimension}...")
        with self.driver.session() as session:
            query = """
            CREATE VECTOR INDEX comment_embedding IF NOT EXISTS
            FOR (c:Comment)
            ON (c.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dim,
                `vector.similarity_function`: 'cosine'
            }}
            """
            session.run(query, dim=dimension)

    def ingest_ontology(self, ontology_path: Path):
        """Ingesta la estructura de la ontología (Aspectos y sus relaciones) siguiendo el modelo SKOS."""
        if not ontology_path.exists():
            print(f"Warning: No se encontró {ontology_path}. Saltando ingesta de ontología.")
            return

        print(f"Ingestando ontología desde {ontology_path}...")
        with open(ontology_path, "r", encoding="utf-8") as f:
            onto_data = json.load(f)
        
        aspects = onto_data.get("ontologia_aspectos", {})
        relations = onto_data.get("relaciones_aspectos", [])

        with self.driver.session() as session:
            # 0. Crear ConceptSchemes (Estructura Base)
            schemes = [
                {'id': iri('scheme/courseBase'), 'label': 'Course Base'},
                {'id': iri('scheme/courseEdition'), 'label': 'Course Edition'},
                {'id': iri('scheme/thread'), 'label': 'Thread'},
                {'id': iri('scheme/comment'), 'label': 'Comment'},
                {'id': iri('scheme/aspect'), 'label': 'Aspectos'},
                {'id': iri('scheme/polarity'), 'label': 'Polaridad'},
            ]
            for s in schemes:
                session.run("""
                    MERGE (n:ConceptScheme {id: $id}) 
                    ON CREATE SET n.prefLabel = $label
                """, id=s['id'], label=s['label'])

            # 1. Crear Nodos Aspecto y Jerarquía (Padre-Hijo -> BROADER)
            # Definir Scheme Aspect
            scheme_aspect = iri('scheme/aspect')


            for aspect_name, info in aspects.items():
                aspect_uri = iri(f'aspect/{aspect_name}')
                desc = info.get("descripcion", "")
                
                # Crear Nodo Aspecto
                query_node = """
                MERGE (a:Concept {id: $id})
                SET a:Aspect, 
                    a.prefLabel = $label,
                    a.definition = $desc,
                    a.inScheme = $scheme
                """
                session.run(query_node, id=aspect_uri, label=aspect_name, desc=desc, scheme=scheme_aspect)
                
                # Relación con Scheme
                session.run("""
                    MATCH (s:ConceptScheme {id: $scheme})
                    MATCH (a:Concept {id: $id})
                    MERGE (s)-[:HAS_TOP_CONCEPT]->(a)
                """, scheme=scheme_aspect, id=aspect_uri)

                # Relación Jerárquica (BROADER)
                parent_name = info.get("padre")
                if parent_name:
                    parent_uri = iri(f'aspect/{parent_name}')
                    # Asegurar padre (por si el orden de iteración no ayuda, aunque MERGE crea nodos vacíos si no existen, mejor asegurar propiedades luego)
                    # En este caso, asumimos que todos se crearán eventually.
                    # Pero para la relación necesito los nodos.
                    query_rel = """
                    MATCH (child:Concept {id: $child_id})
                    MERGE (parent:Concept {id: $parent_id})
                    MERGE (child)-[:BROADER]->(parent)
                    """
                    session.run(query_rel, child_id=aspect_uri, parent_id=parent_uri)

            # 2. Crear Relaciones Semánticas (RELATED)
            for subj, rel, obj in relations:
                subj_uri = iri(f'aspect/{subj}')
                obj_uri = iri(f'aspect/{obj}')
                
                # Mapeamos relaciones semánticas siempre a RELATED por consistencia con neo4j_builder
                # Si se quisiera preservar el tipo específico, habría que cambiar neo4j_builder también.
                # Aquí usamos RELATED para cumplir con SKOS simple.
                
                query = """
                MATCH (s:Concept {id: $subj_id})
                MATCH (o:Concept {id: $obj_id})
                MERGE (s)-[:RELATED]->(o)
                """
                session.run(query, subj_id=subj_uri, obj_id=obj_uri)
        
        print("Ontología ingestada (Modelo SKOS).")

    def ingest_data(self, data: List[Dict[str, Any]]):
        print(f"Iniciando ingesta de {len(data)} registros de ABSA...")
        
        if not data:
            return

        # Detectar dimensión del vector para crear índice
        # Prioridad: vector_texto (1536) > vector_fusionado (legacy)
        first_vector = data[0].get("vector_texto") or data[0].get("vector_fusionado")
        if first_vector:
            self.create_vector_index(len(first_vector))
        
        with self.driver.session() as session:
            for i, record in enumerate(data):
                if i % 100 == 0:
                    print(f"Procesando registro {i}/{len(data)}...")
                
                # Preparar vectores
                vec_texto = record.get("vector_texto")
                vec_grafo = record.get("vector_grafo")
                vec_fusionado = record.get("vector_fusionado")
                
                # El vector principal para el índice es el de texto (si existe), sino el fusionado
                main_vector = vec_texto if vec_texto else vec_fusionado
                
                session.execute_write(
                    self._ingest_record, 
                    record, 
                    main_vector, 
                    vec_grafo
                )
        
        print("Ingesta de datos completada.")

    def _ingest_record(self, tx, record: Dict[str, Any], vector: List[float], vector_grafo: List[float] = None):
        comment_id_val = str(record.get("id_comentario"))
        
        # Resolución de IDs usando lookup
        lookup_data = self.lookup_map.get(comment_id_val, {})
        
        real_course_id = lookup_data.get("course_id")
        real_thread_id = lookup_data.get("thread_id")
        
        # Fallback al record si no hay en lookup o es None
        course_id_raw = real_course_id if real_course_id else (record.get("course_id") or "UNKNOWN")
        thread_id_val = real_thread_id if real_thread_id else (record.get("thread_id") or "UNKNOWN")
        
        base_course_id = iri(f'courseBase/{record.get("base_course") or "UNKNOWN"}')
        course_edition_id = iri(f'courseEdition/{course_id_raw}')
        thread_uri = iri(f'thread/{thread_id_val}')
        comment_uri = iri(f'comment/{comment_id_val}')
        
        aspect_name = record.get("aspecto")
        aspect_uri = iri(f'aspect/{aspect_name}') if aspect_name else None

        
        query = """
        // 1. Jerarquía de Cursos (SKOS style pero simplificado para evitar re-crear todo el árbol aquí si no existe)
        // Asumimos que la estructura base es similar, pero aquí usamos las etiquetas específicas también para compatibilidad.
        
        MERGE (bc:Concept:CourseBase {id: $bc_id})
        ON CREATE SET bc.prefLabel = $bc_label
        
        MERGE (ce:Concept:CourseEdition {id: $ce_id})
        ON CREATE SET ce.prefLabel = $ce_label
        
        MERGE (ce)-[:BROADER]->(bc) 
        // Nota: neo4j_builder usa BROADER, antes usábamos BELONGS_TO_BASE. Unificamos a BROADER.
        
        // 2. Jerarquía de Hilos
        MERGE (t:Concept:Thread {id: $t_id})
        ON CREATE SET t.prefLabel = $t_label
        
        MERGE (t)-[:BROADER]->(ce)
        
        // 3. Comentario
        MERGE (c:Concept:Comment {id: $c_id})
        SET 
            c.prefLabel = $c_label,
            c.text = $mencion, // Guardamos texto original también
            c.note = $mencion,  // SKOS note
            c.sentiment = $sentiment,
            c.justification = $justification,
            c.confidence = $confidence,
            c.embedding = $vector,
            c.embedding_graph = $vector_grafo
            
        // 4. Relación Comentario -> Hilo
        MERGE (c)-[:BROADER]->(t)
        
        // 5. Relación Comentario -> Aspecto (MENTIONS - Específica de Domain, no SKOS core, pero válida)
        // El aspecto YA DEBE EXISTIR desde ingest_ontology, pero usamos MERGE por seguridad
        """
        
        params = {
            "bc_id": base_course_id, "bc_label": record.get("base_course") or "UNKNOWN",
            "ce_id": course_edition_id, "ce_label": course_id_raw,
            "t_id": thread_uri, "t_label": f"Thread {thread_id_val}",
            "c_id": comment_uri, "c_label": f"Comment {comment_id_val}",
            "mencion": record.get("mencion"),
            "sentiment": record.get("sentimiento"),
            "justification": record.get("justificacion"),
            "confidence": record.get("confianza"),
            "vector": vector,
            "vector_grafo": vector_grafo
        }

        tx.run(query, **params)
        
        # Link to Aspect if exists
        if aspect_uri:
            query_aspect = """
            MATCH (c:Concept:Comment {id: $c_id})
            MERGE (a:Concept {id: $a_id}) 
            // Aseguramos etiqueta Aspect por si acaso no se corrió ontología
            SET a:Aspect 
            MERGE (c)-[:MENTIONS {sentiment: $sentiment}]->(a)
            """
            tx.run(query_aspect, c_id=comment_uri, a_id=aspect_uri, sentiment=record.get("sentimiento"))

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingesta a Neo4j")
    parser.add_argument("--input-dir", type=str, help="Directorio con archivos JSON a ingestar")
    parser.add_argument("--input-file", type=str, help="Archivo único JSON a ingestar")
    parser.add_argument("--lookup-file", type=str, help="Archivo JSON para mapeo de IDs (ej. contenido_curso_srm.json)")
    args = parser.parse_args()

    files_to_ingest = []
    
    # Lógica de resolución de entrada
    if args.input_dir:
        search_path = Path(args.input_dir)
        if search_path.exists():
            # Buscar chunks primero
            chunks = list(search_path.glob("resultados_absa_part_*.json"))
            if chunks:
                files_to_ingest = sorted(chunks)
                print(f"Detectados {len(files_to_ingest)} chunks en {search_path}")
            else:
                # Si no hay chunks, buscar cualquier json
                all_jsons = list(search_path.glob("*.json"))
                files_to_ingest = sorted(all_jsons)
                print(f"Detectados {len(files_to_ingest)} archivos JSON en {search_path}")
    elif args.input_file:
        fpath = Path(args.input_file)
        if fpath.exists():
            files_to_ingest.append(fpath)
    else:
        # Fallback original
        search_dir = INPUT_FILE.parent
        if search_dir.exists():
            chunks = list(search_dir.glob("resultados_absa_part_*.json"))
            if chunks:
                files_to_ingest = sorted(chunks)
                print(f"Detectados {len(files_to_ingest)} archivos chunk para ingestión (Default).")
            elif INPUT_FILE.exists():
                 files_to_ingest.append(INPUT_FILE)
                 print(f"Usando archivo único default: {INPUT_FILE}")

    if not files_to_ingest:
        print("Error: No se encontraron archivos para ingestar.")
        print("Usa --input-dir o --input-file, o asegura que existan los defaults.")
        return

    ingester = Neo4jIngester(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    if args.lookup_file:
        ingester.load_lookup_map(Path(args.lookup_file))

    try:
        ingester.setup_schema()
        # Primero ingestamos la ontología para asegurar que los Aspectos existan con sus propiedades
        ingester.ingest_ontology(ONTOLOGY_FILE)
        
        # Luego los datos transaccionales, archivo por archivo
        total_files = len(files_to_ingest)
        for idx, file_path in enumerate(files_to_ingest, 1):
            print(f"\n[Archivo {idx}/{total_files}] Leyendo {file_path.name}...")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                print(f"   Ingestando {len(data)} registros...")
                ingester.ingest_data(data)
                print(f"   [OK] Ingesta completada para {file_path.name}")
                
            except json.JSONDecodeError:
                print(f"   [ERROR] Archivo JSON corrupto: {file_path.name}")
            except Exception as e:
                print(f"   [ERROR] Falló la ingesta de {file_path.name}: {e}")

    except Exception as e:
        print(f"Error crítico durante el proceso de ingesta: {e}")
    finally:
        ingester.close()

if __name__ == "__main__":
    main()
