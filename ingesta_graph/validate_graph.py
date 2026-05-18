#!/usr/bin/env python3
"""
Script de Validación del Grafo Neo4j (TIC-ABSA-KG).

Ejecuta una batería de consultas Cypher para verificar:
1. La estructura de la ontología (Aspectos, Esquemas).
2. La integridad de los datos ingestados (Comentarios, Cursos).
3. Las relaciones críticas (MENTIONS hacia Aspectos).
4. Estadísticas globales.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: La librería 'neo4j' no está instalada.")
    sys.exit(1)

# Cargar variables de entorno
load_dotenv()

# Intentar cargar configuración
try:
    from config import NEO4J_URI as CONFIG_NEO4J_URI
    from config import NEO4J_USER as CONFIG_NEO4J_USER
    from config import NEO4J_PASSWORD as CONFIG_NEO4J_PASSWORD
except ImportError:
    CONFIG_NEO4J_URI = "bolt://localhost:7687"
    CONFIG_NEO4J_USER = "neo4j"
    CONFIG_NEO4J_PASSWORD = "password"

NEO4J_URI = os.getenv("NEO4J_URI") or CONFIG_NEO4J_URI
NEO4J_USER = os.getenv("NEO4J_USER") or CONFIG_NEO4J_USER
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") or CONFIG_NEO4J_PASSWORD

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 50)

VALIDATION_QUERIES = [
    {
        "name": "1. Esquemas de Conceptos (ConceptSchemes)",
        "description": "Verificar que existen los esquemas principales (Aspectos, Cursos, Polaridad, etc.)",
        "query": """
            MATCH (s:ConceptScheme) 
            RETURN s.id AS ID, s.prefLabel AS Label
            ORDER BY s.prefLabel
        """,
        "min_rows": 5
    },
    {
        "name": "2. Jerarquía de Aspectos (Roots)",
        "description": "Verificar aspectos raíz (sin padre BROADER)",
        "query": """
            MATCH (root:Concept:Aspect)
            WHERE NOT (root)-[:BROADER]->(:Concept:Aspect)
            RETURN root.prefLabel AS RootAspect, root.id AS ID
        """,
        "min_rows": 1
    },
    {
        "name": "3. Relaciones Semánticas (RELATED)",
        "description": "Verificar relaciones no jerárquicas entre aspectos",
        "query": """
             MATCH (a:Concept:Aspect)-[r:RELATED]->(b:Concept:Aspect)
             RETURN a.prefLabel AS From, type(r) AS Rel, b.prefLabel AS To
             LIMIT 10
        """,
        "min_rows": 1
    },
    {
        "name": "4. Jerarquía de Cursos (Muestra)",
        "description": "Verificar conexión Base -> Edition -> Thread",
        "query": """
            MATCH path = (t:Thread)-[:BROADER]->(ce:CourseEdition)-[:BROADER]->(cb:Concept:CourseBase)
            RETURN cb.prefLabel as Base, ce.prefLabel as Edition, t.prefLabel as Thread
            LIMIT 5
        """,
        "min_rows": 1
    },
    {
        "name": "5. Comentarios Ingestados",
        "description": "Verificar nodos, texto y etiquetas de Comentarios",
        "query": """
            MATCH (c:Concept:Comment)
            RETURN c.id AS ID, labels(c) AS Labels, substring(c.text, 0, 50) AS Snippet
            LIMIT 5
        """,
        "min_rows": 1
    },
    {
        "name": "6. Vínculos Críticos (MENTIONS)",
        "description": "Verificar que los comentarios se conectan con Aspectos (RAG funcional)",
        "query": """
            MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
            RETURN c.id AS CommentID, r.sentiment AS Sentiment, a.prefLabel AS Aspect
            LIMIT 5
        """,
        "min_rows": 1
    },
    {
        "name": "7. Comentarios Huérfanos (Orphans)",
        "description": "Comentarios SIN vínculo a Aspectos (Warning si son muchos)",
        "query": """
            MATCH (c:Concept:Comment)
            WHERE NOT (c)-[:MENTIONS]->(:Concept:Aspect)
            RETURN count(c) AS OrphanCount
        """,
        "min_rows": 0 
    },
    {
        "name": "8. Estadísticas Globales",
        "description": "Conteo total de Nodos por Etiqueta",
        "query": """
            MATCH (n)
            RETURN labels(n) AS Labels, count(*) AS Total
            ORDER BY Total DESC
        """,
        "min_rows": 1
    }
]

def run_validations():
    print("="*60)
    print(f"Iniciando Validación del Grafo: {NEO4J_URI}")
    print("="*60)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    all_passed = True
    
    try:
        with driver.session() as session:
            for check in VALIDATION_QUERIES:
                print(f"\n>> {check['name']}")
                print(f"   Desc: {check['description']}")
                
                try:
                    result = session.run(check["query"])
                    data = [dict(record) for record in result]
                    df = pd.DataFrame(data)
                    
                    count = len(df)
                    min_req = check.get("min_rows", 0)
                    
                    if count >= min_req:
                        status = "[PASS]"
                    else:
                        status = "[FAIL]" if min_req > 0 else "[INFO]"
                        all_passed = False if min_req > 0 else all_passed
                    
                    print(f"   Rows: {count}  Status: {status}")
                    
                    if not df.empty:
                        print(df.to_string(index=False))
                    elif count == 0 and min_req > 0:
                        print("   !!! No se encontraron resultados (Esperado > 0) !!!")
                        
                except Exception as e:
                    print(f"   [ERROR] Falló la consulta: {e}")
                    all_passed = False
                    
    finally:
        driver.close()
        
    print("\n" + "="*60)
    if all_passed:
        print("RESUMEN: VALIDACIÓN EXITOSA (Todos los checks pasaron)")
    else:
        print("RESUMEN: ADVERTENCIAS ENCONTRADAS (Revisar [FAIL])")
    print("="*60)

if __name__ == "__main__":
    run_validations()
