import sys
import os
import time
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.rag.rag_engine import GraphRAGEngine

def test_phase3():
    print("=== Testing Phase 3 Performance ===")
    
    try:
        engine = GraphRAGEngine()
        
        # 1. Test Embedding Caching
        print("\n[TEST 1] Embedding Caching...")
        query_text = "Qué dicen sobre la evaluación?"
        
        # First call (uncached)
        start_time = time.time()
        engine.query(query_text)
        duration_1 = time.time() - start_time
        print(f"First call duration: {duration_1:.4f}s")
        
        # Second call (cached)
        start_time = time.time()
        engine.query(query_text)
        duration_2 = time.time() - start_time
        print(f"Second call duration: {duration_2:.4f}s")
        
        # Check if second call was significantly faster (or at least used cache logic)
        # Note: Network latency might vary, but we look for the cache log print in stdout
        print("Check console output for '[CACHE] Usando embedding en caché.'")
        
        # 2. Verify Indexes
        print("\n[TEST 2] Verifying Indexes...")
        with engine.driver.session() as session:
            result = session.run("SHOW INDEXES YIELD name, type, labelsOrTypes, properties WHERE type = 'RANGE'")
            # Check for indexed properties
            indexed_props = []
            for record in result:
                if record["labelsOrTypes"] and record["properties"]:
                    label = record["labelsOrTypes"][0]
                    prop = record["properties"][0]
                    indexed_props.append(f"{label}.{prop}")
            
            print(f"Indexed properties: {indexed_props}")
            
            required_props = ["CourseEdition.id", "Comment.sentiment"]
            for prop in required_props:
                if prop in indexed_props:
                    print(f"[PASS] Property '{prop}' is indexed.")
                else:
                    print(f"[FAIL] Property '{prop}' is NOT indexed.")

    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'engine' in locals():
            engine.close()

if __name__ == "__main__":
    test_phase3()
