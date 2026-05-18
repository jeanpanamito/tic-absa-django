import os
import sys
from neo4j import GraphDatabase

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
except ImportError:
    print("Error importing config. Using defaults/env.")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

def validate():
    print(f"Connecting to {NEO4J_URI} as {NEO4J_USER}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("Connection successful.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    with driver.session() as session:
        # 1. Counts
        print("\n--- Node Counts ---")
        for label in ["BaseCourse", "CourseEdition", "Thread", "Comment", "Aspect"]:
            try:
                count = session.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
                print(f"{label}: {count}")
            except Exception as e:
                print(f"Error counting {label}: {e}")
            
        # 2. Relationship Counts
        print("\n--- Relationship Counts ---")
        try:
            rels = session.run("MATCH ()-[r]->() RETURN type(r) as t, count(r) as c ORDER BY c DESC")
            for record in rels:
                print(f"{record['t']}: {record['c']}")
        except Exception as e:
            print(f"Error counting relationships: {e}")

        # 3. Course Details
        print("\n--- Courses & Editions ---")
        try:
            courses = session.run("""
                MATCH (bc:BaseCourse)
                OPTIONAL MATCH (ce:CourseEdition)-[:BELONGS_TO_BASE]->(bc)
                RETURN bc.id as base, collect(ce.id) as editions
            """)
            for record in courses:
                print(f"Base: {record['base']}")
                editions = record['editions']
                print(f"  Editions ({len(editions)}): {editions}")
        except Exception as e:
            print(f"Error fetching courses: {e}")

        # 4. Aspects
        print("\n--- Aspects (Sample) ---")
        try:
            aspects = session.run("MATCH (a:Aspect) RETURN a.name as name LIMIT 10")
            print([r["name"] for r in aspects])
        except Exception as e:
            print(f"Error fetching aspects: {e}")

    driver.close()

if __name__ == "__main__":
    validate()
