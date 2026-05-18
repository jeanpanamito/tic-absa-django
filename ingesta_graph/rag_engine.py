#!/usr/bin/env python3
"""
Motor GraphRAG con LlamaIndex y Neo4j (Driver Nativo).

Este script implementa la lógica de Búsqueda Híbrida (Vector + Grafo) para
responder preguntas sobre el análisis de sentimientos educativo.
Usa el driver de Neo4j directamente para evitar problemas de dependencias.

Requisitos:
  pip install llama-index neo4j python-dotenv
"""

import os
import sys
from typing import List, Optional
from functools import lru_cache
from llama_index.core.llms import ChatMessage, MessageRole

try:
    from neo4j import GraphDatabase
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI
    from llama_index.core import Settings
except ImportError:
    print("Error: Faltan librerías.")
    print("Instala: pip install llama-index neo4j python-dotenv")
    sys.exit(1)

from dotenv import load_dotenv

load_dotenv()

# Configuración
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Intentar cargar desde env, sino desde config
try:
    from config import OPENAI_API_KEY as CONFIG_OPENAI_KEY
except ImportError:
    CONFIG_OPENAI_KEY = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or CONFIG_OPENAI_KEY

print(f"DEBUG: OPENAI_API_KEY found: {bool(OPENAI_API_KEY)}")
if OPENAI_API_KEY:
    print(f"DEBUG: Key starts with: {OPENAI_API_KEY[:10]}...")

# Constantes
MAX_CONTEXT_CHARS = 12000
MAX_RETRIEVED_NODES = 15

# Validación movida a __init__ para no romper importaciones
# if not OPENAI_API_KEY:
#     print("Error: OPENAI_API_KEY no encontrada en variables de entorno.")
#     sys.exit(1)

class GraphRAGEngine:
    def __init__(self, uri=None, user=None, password=None):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no encontrada. Configura la variable de entorno.")

        self.uri = uri or NEO4J_URI
        self.user = user or NEO4J_USER
        self.password = password or NEO4J_PASSWORD

        print(f"Conectando a Neo4j en {self.uri}...")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.verify_connectivity()
        
        self.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
        self.llm = OpenAI(model="gpt-4o-mini", temperature=0)
        
        # Cache simple en memoria para embeddings de preguntas frecuentes
        self._embedding_cache = {}

    def verify_connectivity(self):
        try:
            self.driver.verify_connectivity()
            print("Conectado exitosamente a Neo4j.")
        except Exception as e:
            raise RuntimeError(f"Error conectando a Neo4j: {e}")

    def close(self):
        self.driver.close()

    def validate_course_exists(self, course_id: str) -> bool:
        """Verifica si un curso existe en la base de datos (por prefLabel)."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Concept:CourseEdition) WHERE c.prefLabel = $id RETURN count(c) as count", 
                id=course_id
            ).single()
            return result["count"] > 0

    def _get_cached_embedding(self, text: str) -> List[float]:
        """Obtiene embedding del cache o lo genera."""
        if text in self._embedding_cache:
            print("   [CACHE] Usando embedding en caché.")
            return self._embedding_cache[text]
        
        embedding = self.embed_model.get_query_embedding(text)
        self._embedding_cache[text] = embedding
        return embedding

    def query(self, question: str, course_filter: Optional[str] = None) -> str:
        print(f"\nPregunta: {question}")
        
        if course_filter:
            print(f"Filtro de Curso: {course_filter}")
            if not self.validate_course_exists(course_filter):
                return f"Error: El curso '{course_filter}' no existe en la base de datos."

        print("Generando embedding de la pregunta...")
        query_embedding = self._get_cached_embedding(question)
        
        print("Buscando en Neo4j (Vector + Grafo)...")
        context_list = []
        
        with self.driver.session() as session:
            # Construir cláusula WHERE dinámica
            where_clause = ""
            if course_filter:
                where_clause = f"WHERE course.prefLabel = '{course_filter}'"

            # Consulta Híbrida con LÍMITE explícito
            # SKOS Update: 
            # - Etiquetas: Concept, Comment, CourseEdition, Aspect
            # - Relaciones: BROADER (Path: Comment -> Thread -> CourseEdition)
            # - Propiedades: prefLabel en lugar de name/id para display
            
            query_cypher = f"""
                CALL db.index.vector.queryNodes('comment_embedding', $limit, $embedding)
                YIELD node, score
                MATCH (node:Concept:Comment)-[:MENTIONS]->(aspect:Concept:Aspect)
                OPTIONAL MATCH (node)-[:BROADER]->(thread:Concept:Thread)-[:BROADER]->(course:Concept:CourseEdition)
                {where_clause}
                RETURN 
                    node.text as text, 
                    aspect.prefLabel as aspect, 
                    node.sentiment as sentiment, 
                    node.justification as justification,
                    coalesce(course.prefLabel, 'Unknown') as course,
                    score
            """
            
            result = session.run(
                query_cypher, 
                embedding=query_embedding, 
                limit=MAX_RETRIEVED_NODES
            )
            
            current_chars = 0
            for record in result:
                item = (
                    f"- Comentario: \"{record['text']}\"\n"
                    f"  Aspecto: {record['aspect']} ({record['sentiment']})\n"
                    f"  Curso: {record['course']}\n"
                    f"  Justificación: {record['justification']}\n"
                    f"  Similitud: {record['score']:.4f}"
                )
                
                # Control de límite de contexto
                if current_chars + len(item) > MAX_CONTEXT_CHARS:
                    print(f"   [INFO] Límite de contexto alcanzado ({current_chars} chars).")
                    break
                
                context_list.append(item)
                current_chars += len(item)
            
            if not context_list:
                return "No se encontró información relevante en la base de datos."

            context_str = "\n\n".join(context_list)

        # Generación de respuesta usando Chat API
        print("Generando respuesta con LLM (Chat API)...")
        
        system_prompt = """Eres un experto en análisis educativo. Tu misión es responder preguntas basándote ÚNICAMENTE en el contexto proporcionado del grafo de conocimiento.
        
        Reglas:
        1. Si la respuesta no está en el contexto, di "No tengo información suficiente en la base de datos".
        2. Cita ejemplos específicos del contexto cuando sea posible.
        3. Mantén un tono profesional y objetivo.
        4. Si hay un filtro de curso activo, asegúrate de que la respuesta se centre en ese contexto."""

        user_prompt = f"""CONTEXTO RECUPERADO:
        {context_str}
        
        PREGUNTA DEL USUARIO: 
        {question}"""
        
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]
        
        response = self.llm.chat(messages)
        return str(response.message.content)

    def get_course_report(self, course_id: str) -> str:
        print(f"\nGenerando reporte para el curso: {course_id}")
        
        with self.driver.session() as session:
            # 1. Verificar existencia y metadatos (BaseCourse via BROADER)
            # SKOS: CourseEdition -> BROADER -> BaseCourse
            meta_result = session.run("""
                MATCH (ce:Concept:CourseEdition {prefLabel: $cid})-[:BROADER]->(bc:Concept:CourseBase)
                RETURN ce.prefLabel as edition, bc.prefLabel as base
            """, cid=course_id).single()
            
            if not meta_result:
                # Intento fallback sin base course si no existe relación
                return f"Error: No se encontró el curso con ID '{course_id}' o falló la relación con BaseCourse."
            
            base_course = meta_result["base"]
            
            # 2. Estadísticas de Sentimiento
            # Path: Comment -> Thread -> CourseEdition (usando BROADER in reverse)
            stats_result = session.run("""
                MATCH (ce:Concept:CourseEdition {prefLabel: $cid})<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment)
                RETURN c.sentiment as sentiment, count(*) as count
            """, cid=course_id)
            
            sentiment_counts = {r["sentiment"]: r["count"] for r in stats_result}
            total_comments = sum(sentiment_counts.values())
            
            if total_comments == 0:
                 return f"Reporte para '{course_id}': El curso existe pero no tiene comentarios registrados."

            # 3. Top Aspectos Negativos (Pain Points)
            neg_aspects_result = session.run("""
                MATCH (ce:Concept:CourseEdition {prefLabel: $cid})<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment)
                MATCH (c)-[r:MENTIONS]->(a:Concept:Aspect)
                WHERE r.sentiment = 'Negativo'
                RETURN a.prefLabel as aspect, count(*) as count
                ORDER BY count DESC LIMIT 5
            """, cid=course_id)
            neg_aspects = [f"{r['aspect']} ({r['count']})" for r in neg_aspects_result]
            
            # 4. Top Aspectos Positivos (Strengths)
            pos_aspects_result = session.run("""
                MATCH (ce:Concept:CourseEdition {prefLabel: $cid})<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment)
                MATCH (c)-[r:MENTIONS]->(a:Concept:Aspect)
                WHERE r.sentiment = 'Positivo'
                RETURN a.prefLabel as aspect, count(*) as count
                ORDER BY count DESC LIMIT 5
            """, cid=course_id)
            pos_aspects = [f"{r['aspect']} ({r['count']})" for r in pos_aspects_result]

        # Generar Resumen con LLM
        print("Sintetizando reporte con LLM...")
        prompt = f"""
        Genera un reporte ejecutivo breve para el curso "{course_id}" (Base: {base_course}).
        
        DATOS:
        - Total Comentarios: {total_comments}
        - Sentimientos: {sentiment_counts}
        - Principales Quejas (Top 5): {', '.join(neg_aspects)}
        - Principales Fortalezas (Top 5): {', '.join(pos_aspects)}
        
        Estructura el reporte en:
        1. Resumen General
        2. Puntos Críticos (Quejas)
        3. Aciertos (Fortalezas)
        4. Recomendación breve
        """
        
        response = self.llm.complete(prompt)
        return str(response)

def main():
    engine = None
    try:
        engine = GraphRAGEngine()
        
        # Ejemplo de uso interactivo
        print("\n=== Sistema GraphRAG Educativo ===")
        print("Escribe 'exit' para salir.\n")
        
        # Si se pasa un argumento, usarlo como query única
        if len(sys.argv) > 1:
            q = " ".join(sys.argv[1:])
            respuesta = engine.query(q)
            print(f"\nRespuesta:\n{respuesta}\n")
            return

        while True:
            q = input("Consulta >> ")
            if q.lower() in ["exit", "quit"]:
                break
            
            if not q.strip():
                continue
                
            respuesta = engine.query(q)
            print(f"\nRespuesta:\n{respuesta}\n")
            print("-" * 50)

    except Exception as e:
        print(f"Error fatal: {e}")
    finally:
        if engine:
            engine.close()

if __name__ == "__main__":
    main()
