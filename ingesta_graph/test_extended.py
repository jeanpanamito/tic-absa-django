#!/usr/bin/env python3
"""
Script de pruebas extendidas para GraphRAG.
Cubre: Reportes de diferentes cursos, consultas globales vs filtradas, y manejo de errores.
"""
import sys
import os
from rag_engine import GraphRAGEngine

# Asegurar que podemos importar rag_engine
sys.path.append(os.path.dirname(__file__))

def run_extended_tests():
    print("=== Iniciando Pruebas Extendidas ===")
    engine = GraphRAGEngine()
    
    # CASO 1: Reporte de un curso diferente
    course_id = "course-v1:UTPL+HG-Ed2+2017_ENE"
    print(f"\n[TEST 1] Generando reporte para {course_id}...")
    try:
        report = engine.get_course_report(course_id)
        print("\n--- REPORTE (HG Ed2) ---")
        print(report[:500] + "...\n(truncado)") # Truncar para no llenar la pantalla
        print("------------------------")
    except Exception as e:
        print(f"ERROR en Test 1: {e}")

    # CASO 2: Consulta Filtrada sobre Evaluación
    question = "¿Qué opinan sobre la evaluación y los exámenes?"
    print(f"\n[TEST 2] Consulta filtrada ({course_id}): '{question}'...")
    try:
        response = engine.query(question, course_filter=course_id)
        print("\n--- RESPUESTA FILTRADA ---")
        print(response)
        print("--------------------------")
    except Exception as e:
        print(f"ERROR en Test 2: {e}")

    # CASO 3: Consulta Global (Sin filtro)
    question_global = "Resumen general de la calidad de los videos en todos los cursos"
    print(f"\n[TEST 3] Consulta Global: '{question_global}'...")
    try:
        response = engine.query(question_global)
        print("\n--- RESPUESTA GLOBAL ---")
        print(response)
        print("------------------------")
    except Exception as e:
        print(f"ERROR en Test 3: {e}")

    # CASO 4: Manejo de Error (Curso Inexistente)
    fake_course = "course-v1:FAKE+COURSE+9999"
    print(f"\n[TEST 4] Probando curso inexistente: {fake_course}...")
    try:
        report = engine.get_course_report(fake_course)
        print(f"Resultado: {report}")
    except Exception as e:
        print(f"Excepción capturada (esperado): {e}")

    engine.close()

if __name__ == "__main__":
    run_extended_tests()
