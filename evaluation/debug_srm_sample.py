import os
import sys
from neo4j import GraphDatabase

try:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
except ImportError:
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "absa2025"

def debug_query():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    print("Testing SRM specific query...")
    
    # 1. Check Comments with Course SRM
    q1 = "MATCH (c:Comment)-[:BROADER]->(:Thread)-[:BROADER]->(ce:CourseEdition) WHERE ce.prefLabel CONTAINS 'SRM' RETURN count(c) as paths, count(DISTINCT c) as distinct_nodes"
    with driver.session() as session:
        r = session.run(q1).single()
        print(f"1. SRM Comments in Hierarchy: Paths={r['paths']}, Unique Nodes={r['distinct_nodes']}")

    # 2. Check Comments with Mentions (Global, then filtering if possible)
    # Since we can't filter by SRM easily without hierarchy, check total with mentions
    q2 = "MATCH (c:Comment)-[:MENTIONS]->(:Aspect) RETURN count(c) as count"
    with driver.session() as session:
        print(f"2. Total Comments with Mentions: {session.run(q2).single()['count']}")
        
    # 3. Check Intersection (without text check)
    q3 = """
        MATCH (c:Comment)-[:MENTIONS]->(:Aspect) 
        MATCH (c)-[:BROADER]->(:Thread)-[:BROADER]->(ce:CourseEdition)
        WHERE ce.prefLabel CONTAINS 'SRM'
        RETURN count(c) as count
    """
    with driver.session() as session:
        print(f"3. SRM Comments with Mentions AND Hierarchy: {session.run(q3).single()['count']}")

    # 5. Inspect Single Node Properties
    print("\n5. Inspecting One SRM Comment:")
    q5 = """
        MATCH (c:Comment)-[:BROADER]->(:Thread)-[:BROADER]->(ce:CourseEdition)
        WHERE ce.prefLabel CONTAINS 'SRM'
        RETURN c, properties(c) as props LIMIT 1
    """
    with driver.session() as session:
        result = session.run(q5)
        for r in result:
            props = r['props']
            print(f"Keys: {list(props.keys())}")
            print(f"Text Value: '{props.get('text', 'N/A')}'")
            print(f"Mencion Value: '{props.get('mencion', 'N/A')}'")


    driver.close()

if __name__ == "__main__":
    debug_query()
