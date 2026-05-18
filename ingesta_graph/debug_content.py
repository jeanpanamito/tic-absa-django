#!/usr/bin/env python3
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "absa2025")

def check_content():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        # Check for any comments mentioning 'Videos'
        # Check for any comments mentioning 'Videos'
        result = session.run("""
            MATCH (c:Comment)
            WHERE c.embedding IS NOT NULL
            RETURN size(c.embedding) as dim, count(*) as count
        """)
        print("--- Dimensiones de Embeddings ---")
        for r in result:
            print(f"Dimension: {r['dim']} | Count: {r['count']}")

    driver.close()

if __name__ == "__main__":
    check_content()
