#!/usr/bin/env python3
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "absa2025")

def check_indexes():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print("--- Índices en Neo4j ---")
        result = session.run("SHOW INDEXES")
        for r in result:
            print(f"Nombre: {r['name']} | Tipo: {r['type']} | Estado: {r['state']}")
            if r['type'] == 'VECTOR':
                # print(f"  Keys: {r.keys()}") # Debug
                # Intentar obtener provider o indexConfig
                print(f"  Provider: {r.get('provider')}")
                print(f"  IndexConfig: {r.get('indexConfig')}")

    driver.close()

if __name__ == "__main__":
    check_indexes()
