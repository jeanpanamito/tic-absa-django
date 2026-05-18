#!/usr/bin/env python3
import os
import time
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "absa2025")

def fix_index():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print("1. Borrando índice anterior...")
        try:
            session.run("DROP INDEX comment_embedding IF EXISTS")
            print("   Index dropped.")
        except Exception as e:
            print(f"   Error dropping index: {e}")

        print("2. Creando índice nuevo (128D, Cosine)...")
        try:
            # Neo4j 5.x syntax
            session.run("""
                CREATE VECTOR INDEX comment_embedding IF NOT EXISTS
                FOR (c:Comment)
                ON (c.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 128,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
            print("   Index created.")
        except Exception as e:
            print(f"   Error creating index: {e}")

        print("3. Esperando a que el índice esté ONLINE...")
        for _ in range(10):
            result = session.run("SHOW INDEXES YIELD name, state, type WHERE name = 'comment_embedding'")
            record = result.single()
            if record and record["state"] == "ONLINE":
                print("   Index is ONLINE.")
                break
            print("   Waiting...")
            time.sleep(1)

        print("4. Probando consulta dummy...")
        # Vector dummy de 128 (no ceros para evitar error de coseno)
        dummy_vec = [0.1] * 128
        result = session.run("""
            CALL db.index.vector.queryNodes('comment_embedding', 5, $vec)
            YIELD node, score
            RETURN node.text, score
        """, vec=dummy_vec)
        
        count = 0
        for r in result:
            count += 1
            print(f"   Match: {r['score']:.4f} | {r['node.text'][:30]}...")
        
        print(f"   Total matches: {count}")

    driver.close()

if __name__ == "__main__":
    fix_index()
