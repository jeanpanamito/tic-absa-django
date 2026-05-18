import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.rag.rag_engine import GraphRAGEngine

def test_phase2():
    print("=== Testing Phase 2 Improvements ===")
    
    try:
        engine = GraphRAGEngine()
        
        # 1. Test Standard Query (Chat API + Context Limit)
        print("\n[TEST 1] Standard Query...")
        response = engine.query("Qué dicen sobre la evaluación?")
        print(f"Response length: {len(response)}")
        assert len(response) > 0
        print("[PASS] Standard Query")

        # 2. Test Invalid Course Filter
        print("\n[TEST 2] Invalid Course Filter...")
        response_invalid = engine.query("Test", course_filter="NON_EXISTENT_COURSE_123")
        print(f"Response: {response_invalid}")
        assert "Error" in response_invalid and "no existe" in response_invalid
        print("[PASS] Invalid Course Filter Validation")

        # 3. Test Valid Course Filter (if data exists)
        # We need a valid course ID. Let's try to find one first.
        print("\n[TEST 3] Valid Course Filter...")
        with engine.driver.session() as session:
            result = session.run("MATCH (c:CourseEdition) RETURN c.id as id LIMIT 1").single()
            if result:
                course_id = result["id"]
                print(f"Testing with course: {course_id}")
                response_valid = engine.query("Resumen", course_filter=course_id)
                print(f"Response length: {len(response_valid)}")
                assert "Error" not in response_valid
                print("[PASS] Valid Course Filter")
            else:
                print("[SKIP] No courses found in DB to test filter.")

    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'engine' in locals():
            engine.close()

if __name__ == "__main__":
    test_phase2()
