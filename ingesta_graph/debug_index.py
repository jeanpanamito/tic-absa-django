from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    result = session.run("SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options WHERE type = 'VECTOR'")
    for record in result:
        print(f"Index: {record['name']}")
        print(f"Type: {record['type']}")
        print(f"Labels: {record['labelsOrTypes']}")
        print(f"Properties: {record['properties']}")
        print(f"Options: {record['options']}")
        print("-" * 20)

driver.close()
