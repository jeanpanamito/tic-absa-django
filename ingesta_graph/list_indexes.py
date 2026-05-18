from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    print("Listing ALL indexes:")
    result = session.run("SHOW INDEXES")
    for record in result:
        print(f"Name: {record['name']}, Type: {record['type']}, Labels: {record['labelsOrTypes']}, Properties: {record['properties']}")

driver.close()
