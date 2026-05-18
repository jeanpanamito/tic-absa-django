#!/usr/bin/env python3
"""
Script de prueba para las nuevas funcionalidades de reporte por curso y filtrado.
"""
import sys
import os
from rag_engine import GraphRAGEngine

# Asegurar que podemos importar rag_engine
sys.path.append(os.path.dirname(__file__))

def test_features():
    print("=== Iniciando Pruebas de Reporte y Filtrado ===")
    engine = GraphRAGEngine()
    
    # 1. Prueba de Reporte por Curso
    course_id = "course-v1:UTPL+HG+2016" # ID conocido del dataset de prueba
    print(f"\n[TEST 1] Generando reporte para {course_id}...")
    try:
        report = engine.get_course_report(course_id)
        print("\n--- REPORTE GENERADO ---")
        print(report)
        print("------------------------")
    except Exception as e:
        print(f"ERROR en reporte: {e}")

    # 2. Prueba de Consulta Filtrada
    question = "problemas subir video"
    print(f"\n[TEST 2] Consulta filtrada para {course_id}: '{question}'...")
    try:
        response = engine.query(question, course_filter=course_id)
        print("\n--- RESPUESTA FILTRADA ---")
        print(response)
        print("--------------------------")
    except Exception as e:
        print(f"ERROR en consulta filtrada: {e}")

    engine.close()

if __name__ == "__main__":
    test_features()
