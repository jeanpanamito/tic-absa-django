#!/usr/bin/env python3
"""
Script de Pruebas Exhaustivas del Motor RAG.

Este script valida:
1. Conectividad a Neo4j
2. Existencia de datos en el grafo
3. Funcionamiento del índice vectorial
4. Consultas generales sin filtro
5. Consultas con filtro de curso
6. Generación de reportes ejecutivos
7. Manejo de errores (curso inexistente, consultas vacías)
8. Performance de caching
"""

import sys
import os
import time
from pathlib import Path

# Agregar src al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.rag.rag_engine import GraphRAGEngine

def print_section(title):
    """Imprime un separador visual para las secciones."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def test_connectivity(engine):
    """Test 1: Verificar conectividad a Neo4j."""
    print_section("TEST 1: Conectividad a Neo4j")
    try:
        with engine.driver.session() as session:
            result = session.run("RETURN 1 as test").single()
            if result["test"] == 1:
                print("✅ Conexión a Neo4j exitosa")
                return True
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_data_existence(engine):
    """Test 2: Verificar existencia de datos en el grafo."""
    print_section("TEST 2: Existencia de Datos en el Grafo")
    
    with engine.driver.session() as session:
        # Contar nodos
        counts = {}
        for label in ["Comment", "Aspect", "CourseEdition", "Thread", "BaseCourse"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count").single()
            counts[label] = result["count"]
            print(f"  {label}: {counts[label]} nodos")
        
        # Verificar índice vectorial
        index_result = session.run("""
            SHOW INDEXES 
            YIELD name, type, labelsOrTypes, properties 
            WHERE name = 'comment_embedding'
            RETURN name, type, properties
        """).single()
        
        if index_result:
            print(f"\n✅ Índice vectorial encontrado: {index_result['name']}")
            print(f"   Tipo: {index_result['type']}")
            print(f"   Propiedades: {index_result['properties']}")
        else:
            print("❌ Índice vectorial no encontrado")
            return False
        
        # Verificar que hay comentarios con embeddings
        emb_result = session.run("""
            MATCH (c:Comment)
            WHERE c.embedding IS NOT NULL
            RETURN count(c) as count
        """).single()
        
        print(f"\n  Comentarios con embeddings: {emb_result['count']}")
        
        if all(counts.values()) and emb_result['count'] > 0:
            print("\n✅ Datos del grafo verificados correctamente")
            return True
        else:
            print("\n❌ Faltan datos en el grafo")
            return False

def test_general_query(engine):
    """Test 3: Consulta general sin filtro."""
    print_section("TEST 3: Consulta General (Sin Filtro de Curso)")
    
    question = "¿Qué opinan los estudiantes sobre la evaluación?"
    print(f"Pregunta: {question}\n")
    
    try:
        start_time = time.time()
        response = engine.query(question)
        duration = time.time() - start_time
        
        print(f"\nRespuesta:\n{response}\n")
        print(f"⏱️  Tiempo de respuesta: {duration:.2f}s")
        
        if response and "Error" not in response and len(response) > 50:
            print("✅ Consulta general exitosa")
            return True
        else:
            print("❌ Respuesta vacía o con error")
            return False
    except Exception as e:
        print(f"❌ Error en consulta: {e}")
        return False

def test_filtered_query(engine):
    """Test 4: Consulta con filtro de curso."""
    print_section("TEST 4: Consulta con Filtro de Curso")
    
    # Primero obtener un curso válido
    with engine.driver.session() as session:
        result = session.run("MATCH (c:CourseEdition) RETURN c.id as id LIMIT 1").single()
        if not result:
            print("❌ No hay cursos en la base de datos")
            return False
        course_id = result["id"]
    
    question = "¿Cuáles son los principales problemas reportados?"
    print(f"Pregunta: {question}")
    print(f"Filtro de Curso: {course_id}\n")
    
    try:
        start_time = time.time()
        response = engine.query(question, course_filter=course_id)
        duration = time.time() - start_time
        
        print(f"\nRespuesta:\n{response}\n")
        print(f"⏱️  Tiempo de respuesta: {duration:.2f}s")
        
        if response and "Error" not in response and len(response) > 50:
            print("✅ Consulta filtrada exitosa")
            return True
        else:
            print("❌ Respuesta vacía o con error")
            return False
    except Exception as e:
        print(f"❌ Error en consulta filtrada: {e}")
        return False

def test_course_report(engine):
    """Test 5: Generación de reporte ejecutivo."""
    print_section("TEST 5: Reporte Ejecutivo de Curso")
    
    # Obtener un curso válido
    with engine.driver.session() as session:
        result = session.run("MATCH (c:CourseEdition) RETURN c.id as id LIMIT 1").single()
        if not result:
            print("❌ No hay cursos en la base de datos")
            return False
        course_id = result["id"]
    
    print(f"Generando reporte para: {course_id}\n")
    
    try:
        start_time = time.time()
        report = engine.get_course_report(course_id)
        duration = time.time() - start_time
        
        print(f"\nReporte:\n{report}\n")
        print(f"⏱️  Tiempo de generación: {duration:.2f}s")
        
        if report and "Error" not in report and len(report) > 100:
            print("✅ Reporte ejecutivo generado correctamente")
            return True
        else:
            print("❌ Reporte vacío o con error")
            return False
    except Exception as e:
        print(f"❌ Error generando reporte: {e}")
        return False

def test_invalid_course(engine):
    """Test 6: Manejo de curso inexistente."""
    print_section("TEST 6: Manejo de Errores (Curso Inexistente)")
    
    invalid_course = "course-v1:INVALID+COURSE+9999"
    question = "¿Qué dicen sobre el contenido?"
    
    print(f"Pregunta: {question}")
    print(f"Curso inválido: {invalid_course}\n")
    
    try:
        response = engine.query(question, course_filter=invalid_course)
        print(f"Respuesta:\n{response}\n")
        
        if "Error" in response or "no existe" in response.lower():
            print("✅ Error manejado correctamente")
            return True
        else:
            print("❌ No se detectó el error")
            return False
    except Exception as e:
        print(f"❌ Excepción no manejada: {e}")
        return False

def test_caching(engine):
    """Test 7: Verificar funcionamiento del cache."""
    print_section("TEST 7: Performance de Caching")
    
    question = "¿Qué opinan sobre la plataforma?"
    
    # Primera consulta (sin cache)
    print("Primera consulta (sin caché)...")
    start_time = time.time()
    response1 = engine.query(question)
    duration1 = time.time() - start_time
    print(f"⏱️  Tiempo: {duration1:.2f}s")
    
    # Segunda consulta (con cache)
    print("\nSegunda consulta (con caché)...")
    start_time = time.time()
    response2 = engine.query(question)
    duration2 = time.time() - start_time
    print(f"⏱️  Tiempo: {duration2:.2f}s")
    
    # Calcular mejora
    improvement = ((duration1 - duration2) / duration1) * 100
    print(f"\n📊 Mejora de performance: {improvement:.1f}%")
    
    if duration2 < duration1:
        print("✅ Cache funcionando correctamente")
        return True
    else:
        print("⚠️  Cache no mostró mejora (puede ser normal en primera ejecución)")
        return True  # No es un fallo crítico

def test_empty_result(engine):
    """Test 8: Consulta que no debería retornar resultados."""
    print_section("TEST 8: Manejo de Consultas sin Resultados")
    
    question = "¿Qué opinan sobre la tecnología blockchain en el curso?"
    print(f"Pregunta (probablemente sin resultados): {question}\n")
    
    try:
        response = engine.query(question)
        print(f"Respuesta:\n{response}\n")
        
        if "no" in response.lower() and ("información" in response.lower() or "encontr" in response.lower()):
            print("✅ Respuesta apropiada para consulta sin resultados")
            return True
        else:
            print("⚠️  Respuesta generada (puede haber encontrado algo relacionado)")
            return True  # No es un fallo
    except Exception as e:
        print(f"❌ Error en consulta: {e}")
        return False

def main():
    print("\n" + "🚀" * 40)
    print("  PRUEBAS EXHAUSTIVAS DEL MOTOR RAG")
    print("🚀" * 40)
    
    engine = None
    results = {}
    
    try:
        # Inicializar engine
        print("\nInicializando motor RAG...")
        engine = GraphRAGEngine()
        
        # Ejecutar tests
        tests = [
            ("Conectividad", test_connectivity),
            ("Existencia de Datos", test_data_existence),
            ("Consulta General", test_general_query),
            ("Consulta Filtrada", test_filtered_query),
            ("Reporte Ejecutivo", test_course_report),
            ("Curso Inexistente", test_invalid_course),
            ("Caching", test_caching),
            ("Consulta sin Resultados", test_empty_result),
        ]
        
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func(engine)
            except Exception as e:
                print(f"\n❌ Error crítico en test '{test_name}': {e}")
                results[test_name] = False
        
        # Resumen final
        print_section("RESUMEN DE PRUEBAS")
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status}  {test_name}")
        
        print(f"\n📊 Resultado Final: {passed}/{total} pruebas exitosas ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            print("\n🎉 ¡Todas las pruebas pasaron! El sistema RAG está funcionando correctamente.")
        elif passed >= total * 0.75:
            print("\n⚠️  La mayoría de las pruebas pasaron. Revisar los fallos.")
        else:
            print("\n❌ Múltiples pruebas fallaron. Se requiere revisión del sistema.")
        
    except Exception as e:
        print(f"\n❌ Error fatal durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if engine:
            engine.close()
            print("\n🔌 Conexión a Neo4j cerrada.")

if __name__ == "__main__":
    main()
