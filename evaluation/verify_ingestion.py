import os
import sys
from neo4j import GraphDatabase

try:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
except ImportError:
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "absa2025"

# Ensure we use variables with same names as ingested script might expect for consistency
CONFIG_NEO4J_URI = NEO4J_URI
CONFIG_NEO4J_USER = NEO4J_USER
CONFIG_NEO4J_PASSWORD = NEO4J_PASSWORD

NEO4J_URI = os.getenv("NEO4J_URI") or CONFIG_NEO4J_URI
NEO4J_USER = os.getenv("NEO4J_USER") or CONFIG_NEO4J_USER
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") or CONFIG_NEO4J_PASSWORD

def verify_ingestion():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    queries = {
        "Total Comments": "MATCH (c:Comment) RETURN count(c) as count",
        "Total Threads": "MATCH (t:Thread) RETURN count(t) as count",
        "Total CourseEditions": "MATCH (ce:CourseEdition) RETURN count(ce) as count",
        "Total BaseCourses": "MATCH (bc:CourseBase) RETURN count(bc) as count",
        "Total Aspects": "MATCH (a:Aspect) RETURN count(a) as count",
        "Comments with Embeddings": "MATCH (c:Comment) WHERE c.embedding IS NOT NULL RETURN count(c) as count",
        "Mentions by Course": "MATCH (ce:CourseEdition)<-[:BROADER]-(t:Thread)<-[:BROADER]-(c:Comment)-[:MENTIONS]->(a:Aspect) RETURN ce.prefLabel as curso, count(a) as mentions ORDER BY mentions DESC LIMIT 20",
        "Course Edition Distribution": "MATCH (ce:CourseEdition)<-[:BROADER]-(t:Thread)<-[:BROADER]-(c:Comment) RETURN ce.prefLabel as curso, count(c) as comments ORDER BY comments DESC LIMIT 50"
    }
    
    print("=== Verification Results ===")
    with driver.session() as session:
        for name, query in queries.items():
            result = session.run(query)
            if "Distribution" in name or "Mentions" in name:
                print(f"\n{name}:")
                for record in result:
                    # Handle different column names dynamically if needed, or hardcode based on query
                    qt = "comments" if "comments" in record.keys() else "mentions"
                    print(f"  - {record['curso']}: {record[qt]}")
            else:
                count = result.single()["count"]
                print(f"{name}: {count}")

        # Check Hierarchy Integrity
        print("\nChecking Hierarchy Integrity (Sample)...")
        sample_query = """
        MATCH p=(c:Comment)-[:BROADER]->(t:Thread)-[:BROADER]->(ce:CourseEdition)-[:BROADER]->(bc:CourseBase)
        RETURN bc.prefLabel as base, ce.prefLabel as edition, t.prefLabel as thread, c.prefLabel as comment
        LIMIT 5
        """
        result = session.run(sample_query)
        for r in result:
            print(f"Path Verified: {r['base']} -> {r['edition']} -> {r['thread']} -> {r['comment']}")
            
        print("\nVerification Complete.")
    
    driver.close()

if __name__ == "__main__":
    verify_ingestion()
