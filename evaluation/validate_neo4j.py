#!/usr/bin/env python3
"""
Script de Validación ABSA con Neo4j.
Conecta a la base de datos Neo4j para extraer tripletas (Comentario, Aspecto, Sentimiento)
y validarlas utilizando un LLM (GPT-4o) con prompts en español.

Genera métricas detalladas para el Capítulo 5 de la tesis.
"""

import argparse
import json
import os
import sys
import pandas as pd
from typing import List, Dict, Any
from tqdm import tqdm
from pathlib import Path

# Agregar directorio raíz al path para importar config
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j driver no instalado. pip install neo4j")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai sdk no instalado. pip install openai")
    sys.exit(1)

from sklearn.metrics import classification_report, confusion_matrix

# Cargar configuración
try:
    from config import (
        NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENAI_API_KEY
    )
except ImportError:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class ABSAValidator:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, openai_key, model="gpt-4o"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.client = OpenAI(api_key=openai_key)
        self.model = model

    def close(self):
        self.driver.close()

    def fetch_sample(self, limit=100) -> List[Dict]:
        """Obtiene una muestra de comentarios y sus aspectos extraídos desde Neo4j."""
        query = """
        MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
        MATCH (c)-[:BROADER]->(t:Thread)-[:BROADER]->(ce:CourseEdition)
        WHERE c.text IS NOT NULL AND c.text <> ''
        RETURN 
            c.id as id_comentario,
            c.text as texto,
            a.prefLabel as aspecto_detectado,
            r.sentiment as sentimiento_detectado,
            c.justification as justificacion,
            ce.prefLabel as curso
        ORDER BY rand()
        LIMIT $limit
        """
        results = []
        with self.driver.session() as session:
            for record in session.run(query, limit=limit):
                results.append({
                    "id": record["id_comentario"],
                    "text": record["texto"],
                    "aspect": record["aspecto_detectado"],
                    "sentiment": record["sentimiento_detectado"],
                    "justification": record["justificacion"] or "",
                    "course": record["curso"]
                })
        return results

    def llm_judge(self, text: str, aspect: str, sentiment: str) -> Dict:
        """
        Evalúa la precisión de la extracción ABSA usando un LLM como juez experto.
        """
        system_prompt = """Eres un experto lingüista evaluando un sistema de Análisis de Sentimientos Basado en Aspectos (ABSA) para el dominio educativo.
Tu tarea es validar si el sistema ha extraído correctamente el aspecto y el sentimiento de un comentario de un estudiante.

Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{
    "relevancia_aspecto": <int 1-5, donde 1 es totalmente irrelevante/alucinación y 5 es explícito y correcto>,
    "aspecto_correcto": <bool, true si el aspecto extraído corresponde razonablemente al texto, aunque sea implícito>,
    "sentimiento_correcto": <bool, true si la polaridad (Positivo/Negativo/Neutral) es correcta dada la mención>,
    "sentimiento_real": <str, "Positivo", "Negativo" o "Neutral", tu juicio experto>,
    "explicacion": <str, breve justificación en español>
}
"""
        
        user_prompt = f"""
        COMENTARIO: "{text}"
        
        EXTRACCIÓN DEL SISTEMA:
        - Aspecto Detectado: "{aspect}"
        - Sentimiento Detectado: "{sentiment}"
        
        Evalúa la calidad de esta extracción.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error LLM: {e}")
            return {
                "relevancia_aspecto": 0,
                "aspecto_correcto": False,
                "sentimiento_correcto": False,
                "sentimiento_real": "Error",
                "explicacion": f"Fallo en llamada API: {str(e)}"
            }

    def run_validation(self, sample_size=50, output_dir="data/exports/validation"):
        print(f"Conectando a Neo4j en {NEO4J_URI}...")
        try:
            self.driver.verify_connectivity()
        except Exception as e:
            print(f"No se pudo conectar a Neo4j: {e}")
            return

        print(f"Obteniendo muestra de {sample_size} registros...")
        data = self.fetch_sample(limit=sample_size)
        
        if not data:
            print("No se encontraron datos en Neo4j para validar.")
            return

        print("Iniciando evaluación con LLM...")
        results = []
        
        # Contadores rápidos
        correct_aspects = 0
        correct_sentiments = 0

        for item in tqdm(data):
            evaluation = self.llm_judge(item["text"], item["aspect"], item["sentiment"])
            
            # Combinar datos originales con evaluación
            record = item.copy()
            record.update(evaluation)
            results.append(record)
            
            if evaluation.get("aspecto_correcto"):
                correct_aspects += 1
            if evaluation.get("sentimiento_correcto"):
                correct_sentiments += 1

        # Generar Reporte
        self.generate_report(results, output_dir)
        self.close()

    def generate_report(self, results: List[Dict], output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        
        df = pd.DataFrame(results)
        
        # 1. Guardar JSON detallado
        json_path = os.path.join(output_dir, "validation_results_neo4j.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # 2. Calcular Métricas
        total = len(df)
        aspect_acc = (df["aspecto_correcto"].sum() / total) * 100
        sentiment_acc = (df["sentimiento_correcto"].sum() / total) * 100 # Sentimiento correcto dado el aspecto
        avg_relevance = df["relevancia_aspecto"].mean()

        # Métricas de Sentimiento (Matriz de Confusión)
        # Filtramos solo donde el aspecto fue correcto para ser justos con el clasificador de sentimiento
        valid_aspects_df = df[df["aspecto_correcto"] == True]
        if not valid_aspects_df.empty:
            y_true = valid_aspects_df["sentimiento_real"].str.title() # Normalizar
            y_pred = valid_aspects_df["sentiment"].str.title()
            
            # Classification Report
            cls_report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
            conf_matrix = confusion_matrix(y_true, y_pred, labels=["Positivo", "Negativo", "Neutral"])
        else:
            cls_report = {}
            conf_matrix = []

        # 3. Generar Markdown
        md_lines = []
        md_lines.append(f"# Capítulo 5: Validación de Resultados (Neo4j)")
        md_lines.append(f"\n**Fecha**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
        md_lines.append(f"\n## 1. Resumen Ejecutivo")
        md_lines.append(f"- **Muestra Evaluada**: {total} tripletas (Comentario-Aspecto-Sentimiento)")
        md_lines.append(f"- **Precisión en Detección de Aspectos**: {aspect_acc:.2f}%")
        md_lines.append(f"- **Relevancia Promedio del Aspecto (1-5)**: {avg_relevance:.2f}")
        md_lines.append(f"- **Precisión en Clasificación de Sentimiento**: {sentiment_acc:.2f}%")
        
        md_lines.append(f"\n## 2. Análisis por Curso")
        # Agrupar por curso
        course_metrics = df.groupby("course").agg({
            "aspecto_correcto": "mean",
            "sentimiento_correcto": "mean",
            "id": "count"
        }).reset_index()
        course_metrics.columns = ["Curso", "Precisión Aspecto", "Precisión Sentimiento", "Muestras"]
        course_metrics["Precisión Aspecto"] *= 100
        course_metrics["Precisión Sentimiento"] *= 100
        course_metrics = course_metrics.sort_values(by="Muestras", ascending=False)
        
        md_lines.append("\n| Curso | Muestras | Prec. Aspecto (%) | Prec. Sentimiento (%) |")
        md_lines.append("|---|---|---|---|")
        for _, row in course_metrics.iterrows():
            md_lines.append(f"| {row['Curso']} | {row['Muestras']} | {row['Precisión Aspecto']:.2f} | {row['Precisión Sentimiento']:.2f} |")

        md_lines.append(f"\n## 3. Análisis Detallado de Sentimientos (Global)")
        md_lines.append("Métricas calculadas sobre los aspectos correctamente identificados.")
        
        if cls_report:
            md_lines.append("\n| Clase | Versión LLM (Support) | Precision | Recall | F1-Score |")
            md_lines.append("|---|---|---|---|---|")
            for label, metrics in cls_report.items():
                if isinstance(metrics, dict):
                    md_lines.append(f"| {label} | {metrics['support']} | {metrics['precision']:.2f} | {metrics['recall']:.2f} | {metrics['f1-score']:.2f} |")
        
        md_lines.append("\n### Matriz de Confusión")
        md_lines.append("Filas: Real (LLM), Columnas: Predicción (Sistema)")
        md_lines.append("\n| | Positivo (Pred) | Negativo (Pred) | Neutral (Pred) |")
        md_lines.append("|---|---|---|---|")
        if len(conf_matrix) == 3:
            md_lines.append(f"|Positivo (Real)| {conf_matrix[0][0]} | {conf_matrix[0][1]} | {conf_matrix[0][2]} |")
            md_lines.append(f"|Negativo (Real)| {conf_matrix[1][0]} | {conf_matrix[1][1]} | {conf_matrix[1][2]} |")
            md_lines.append(f"|Neutral (Real)| {conf_matrix[2][0]} | {conf_matrix[2][1]} | {conf_matrix[2][2]} |")
        
        md_lines.append(f"\n## 3. Análisis de Errores (Muestras)")
        errors = df[(df["aspecto_correcto"] == False) | (df["sentimiento_correcto"] == False)]
        if not errors.empty:
            md_lines.append("\n| ID | Curso | Texto (Frag.) | Aspecto (Sys) | Sent (Sys) | Sent (Real) | Explicación |")
            md_lines.append("|---|---|---|---|---|---|---|")
            for _, row in errors.head(10).iterrows():
                text_short = row['text'][:30] + "..." if len(row['text']) > 30 else row['text']
                # Escape pipes
                expl = row['explicacion'].replace("|", "-").replace("\n", " ")
                md_lines.append(f"| {row['id']} | {row['course']} | {text_short} | {row['aspect']} | {row['sentiment']} | {row['sentimiento_real']} | {expl} |")
        else:
            md_lines.append("\n*No se detectaron errores en la muestra (¡Perfecto!).*")

        report_path = os.path.join(output_dir, "validation_report_neo4j.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
            
        print("\n" + "=" * 50)
        print("VALIDACIÓN COMPLETADA")
        print(f"Reporte generado en: {report_path}")
        print("=" * 50)

def main():
    parser = argparse.ArgumentParser(description="Validación de ABSA contra Neo4j")
    parser.add_argument("--sample-size", type=int, default=50, help="Tamaño de la muestra a validar")
    parser.add_argument("--output-dir", default="data/exports/validation", help="Directorio de salida")
    
    args = parser.parse_args()
    
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY no encontrada. Configura tu .env o config.py")
        return

    validator = ABSAValidator(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENAI_API_KEY)
    validator.run_validation(sample_size=args.sample_size, output_dir=args.output_dir)

if __name__ == "__main__":
    main()
