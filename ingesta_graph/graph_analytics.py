#!/usr/bin/env python3
"""
Script para consultas puras de Grafo (Analytics).
Demuestra el poder del Grafo de Conocimiento sin usar búsqueda vectorial.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Configuración (Hardcoded fallback para demo rápida si falla .env)
URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "absa2025")

def run_analytics():
    print(f"Conectando a {URI} como {USER}...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    with driver.session() as session:
        # 1. Distribución de Sentimientos por Aspecto
        print("\n=== 1. Distribución de Sentimientos por Aspecto ===")
        result = session.run("""
            MATCH (c:Comment)-[r:MENTIONS]->(a:Aspect)
            RETURN a.name as Aspecto, r.sentiment as Sentimiento, count(*) as Total
            ORDER BY Aspecto, Total DESC
        """)
        
        print(f"{'ASPECTO':<15} | {'SENTIMIENTO':<10} | {'TOTAL'}")
        print("-" * 40)
        for record in result:
            print(f"{record['Aspecto']:<15} | {record['Sentimiento']:<10} | {record['Total']}")

        # 2. Top Aspectos más Criticados (Negativos)
        print("\n=== 2. Top Aspectos con más Quejas (Negativos) ===")
        result = session.run("""
            MATCH (c:Comment)-[r:MENTIONS {sentiment: 'Negativo'}]->(a:Aspect)
            RETURN a.name as Aspecto, count(*) as Quejas
            ORDER BY Quejas DESC
            LIMIT 3
        """)
        
        for record in result:
            print(f"❌ {record['Aspecto']}: {record['Quejas']} quejas")

        # 3. Cursos con más actividad
        print("\n=== 3. Cursos con más Comentarios ===")
        result = session.run("""
            MATCH (c:Comment)-[:BELONGS_TO]->(course:Course)
            RETURN course.id as Curso, count(*) as Total
            ORDER BY Total DESC
            LIMIT 3
        """)
        
        for record in result:
            print(f"📚 {record['Curso']}: {record['Total']} comentarios")

    driver.close()

if __name__ == "__main__":
    run_analytics()
