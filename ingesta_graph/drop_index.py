from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    try:
        session.run("DROP INDEX comment_embedding")
        print("Index 'comment_embedding' dropped successfully.")
    except Exception as e:
        print(f"Error dropping index: {e}")

driver.close()
