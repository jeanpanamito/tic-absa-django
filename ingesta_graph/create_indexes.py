from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(user, password))

def create_indexes():
    print("Creating performance indexes...")
    with driver.session() as session:
        # Index for CourseEdition ID (used in filtering)
        session.run("CREATE INDEX course_edition_id IF NOT EXISTS FOR (c:CourseEdition) ON (c.id)")
        print("- Index 'course_edition_id' created.")
        
        # Index for Comment Sentiment (used in reporting)
        session.run("CREATE INDEX comment_sentiment IF NOT EXISTS FOR (c:Comment) ON (c.sentiment)")
        print("- Index 'comment_sentiment' created.")
        
        # Index for BaseCourse ID (used in hierarchy traversal)
        session.run("CREATE INDEX base_course_id IF NOT EXISTS FOR (b:BaseCourse) ON (b.id)")
        print("- Index 'base_course_id' created.")

    print("All indexes created successfully.")

if __name__ == "__main__":
    try:
        create_indexes()
    except Exception as e:
        print(f"Error creating indexes: {e}")
    finally:
        driver.close()
