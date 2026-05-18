import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.rag.rag_engine import GraphRAGEngine

def validate_course_queries():
    print("=== Validating Course Queries ===")
    
    try:
        engine = GraphRAGEngine()
        
        # 1. Get a valid course ID
        print("\n[STEP 1] Fetching a valid course ID...")
        course_id = None
        with engine.driver.session() as session:
            result = session.run("MATCH (c:CourseEdition) RETURN c.id as id LIMIT 1").single()
            if result:
                course_id = result["id"]
                print(f"Found Course ID: {course_id}")
            else:
                print("[ERROR] No courses found in database. Cannot proceed.")
                return

        # 2. Test Course Report
        print(f"\n[STEP 2] Testing get_course_report('{course_id}')...")
        report = engine.get_course_report(course_id)
        print("-" * 40)
        print(report)
        print("-" * 40)
        
        if "Reporte Ejecutivo" in report or "Error" not in report:
             print("[PASS] Course Report generated.")
        else:
             print("[FAIL] Course Report generation failed.")

        # 3. Test Filtered Query
        print(f"\n[STEP 3] Testing filtered query for '{course_id}'...")
        question = "Cuáles son los aspectos más negativos?"
        response = engine.query(question, course_filter=course_id)
        print("-" * 40)
        print(f"Q: {question}")
        print(f"A: {response}")
        print("-" * 40)
        
        if "Error" not in response:
            print("[PASS] Filtered query successful.")
        else:
            print("[FAIL] Filtered query returned error.")

    except Exception as e:
        print(f"\n[FAIL] Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'engine' in locals():
            engine.close()

if __name__ == "__main__":
    validate_course_queries()
