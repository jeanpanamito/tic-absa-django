"""
RAG Service — Thread-safe singleton for GraphRAG operations.

Adapted from the original rag_engine.py.
Uses hybrid search (vector index + graph traversal) and OpenAI Chat API
to answer questions about the ABSA knowledge graph.

Shares the Neo4j driver with Neo4jService to avoid duplicate connection pools.
"""

import logging
import threading
from typing import List, Optional

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from .neo4j_service import Neo4jService

logger = logging.getLogger('analytics.rag')

# Limits
MAX_CONTEXT_CHARS = 12000
MAX_RETRIEVED_NODES = 15


class RAGService:
    """
    Singleton service for Retrieval-Augmented Generation over the ABSA graph.

    Reuses the Neo4j driver from Neo4jService (no extra pool).
    Caches question embeddings in-memory for repeat queries.
    """

    _instance: Optional['RAGService'] = None
    _lock = threading.Lock()

    # ──────────────────────────────────────────────
    # Singleton lifecycle
    # ──────────────────────────────────────────────

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def initialize(self, openai_api_key: str) -> None:
        """Initialize LLM + embedding models (called once from AppConfig.ready)."""
        if self._initialized:
            return

        if not openai_api_key:
            logger.warning(
                "OPENAI_API_KEY not set — RAG features will be unavailable."
            )
            self._initialized = False
            return

        import openai as openai_lib
        openai_lib.api_key = openai_api_key

        self._neo4j = Neo4jService()
        self.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small",
            api_key=openai_api_key,
        )
        self.llm = OpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=openai_api_key,
        )
        self._embedding_cache: dict = {}
        self._initialized = True
        logger.info("RAG service initialized (embedding + LLM ready).")

    @property
    def is_available(self) -> bool:
        return self._initialized and self._neo4j.is_connected

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _get_driver(self):
        """Get the shared Neo4j driver from Neo4jService."""
        return self._neo4j.driver

    def _get_cached_embedding(self, text: str) -> List[float]:
        """Get embedding from cache or generate a new one."""
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        embedding = self.embed_model.get_query_embedding(text)
        self._embedding_cache[text] = embedding
        return embedding

    def _validate_course_exists(self, course_id: str) -> bool:
        """Check if a course edition exists by prefLabel."""
        with self._get_driver().session() as session:
            result = session.run(
                "MATCH (c:Concept:CourseEdition) WHERE c.prefLabel = $id "
                "RETURN count(c) as count",
                id=course_id,
            ).single()
            return result["count"] > 0

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def query(self, question: str, course_filter: Optional[str] = None) -> str:
        """
        Answer a user question using hybrid vector + graph search.

        1. Embed the question.
        2. Query Neo4j vector index for similar comments.
        3. Traverse graph for context (aspect, course, sentiment).
        4. Send context + question to LLM.
        """
        if not self.is_available:
            return "El motor RAG no está disponible. Verifica la configuración de OpenAI y Neo4j."

        # Validate course filter
        if course_filter:
            if not self._validate_course_exists(course_filter):
                return f"Error: El curso '{course_filter}' no existe en la base de datos."

        query_embedding = self._get_cached_embedding(question)
        context_list: List[str] = []

        with self._get_driver().session() as session:
            where_clause = ""
            if course_filter:
                where_clause = f"WHERE course.prefLabel = '{course_filter}'"

            cypher = f"""
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
                cypher,
                embedding=query_embedding,
                limit=MAX_RETRIEVED_NODES,
            )

            current_chars = 0
            for record in result:
                item = (
                    f'- Comentario: "{record["text"]}"\n'
                    f'  Aspecto: {record["aspect"]} ({record["sentiment"]})\n'
                    f'  Curso: {record["course"]}\n'
                    f'  Justificación: {record["justification"]}\n'
                    f'  Similitud: {record["score"]:.4f}'
                )
                if current_chars + len(item) > MAX_CONTEXT_CHARS:
                    break
                context_list.append(item)
                current_chars += len(item)

        if not context_list:
            return "No se encontró información relevante en la base de datos."

        context_str = "\n\n".join(context_list)

        # LLM generation
        system_prompt = (
            "Eres un experto en análisis educativo. Tu misión es responder preguntas "
            "basándote ÚNICAMENTE en el contexto proporcionado del grafo de conocimiento.\n\n"
            "Reglas:\n"
            '1. Si la respuesta no está en el contexto, di "No tengo información suficiente '
            'en la base de datos".\n'
            "2. Cita ejemplos específicos del contexto cuando sea posible.\n"
            "3. Mantén un tono profesional y objetivo.\n"
            "4. Si hay un filtro de curso activo, asegúrate de que la respuesta se centre "
            "en ese contexto."
        )

        user_prompt = (
            f"CONTEXTO RECUPERADO:\n{context_str}\n\n"
            f"PREGUNTA DEL USUARIO:\n{question}"
        )

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = self.llm.chat(messages)
        return str(response.message.content)

    def get_course_report(self, course_id: str) -> str:
        """Generate an executive report for a specific course edition."""
        if not self.is_available:
            return "El motor RAG no está disponible."

        driver = self._get_driver()

        with driver.session() as session:
            # 1. Course metadata (CourseEdition → BROADER → CourseBase)
            meta = session.run(
                "MATCH (ce:Concept:CourseEdition {prefLabel: $cid})"
                "-[:BROADER]->(bc:Concept:CourseBase) "
                "RETURN ce.prefLabel as edition, bc.prefLabel as base",
                cid=course_id,
            ).single()

            if not meta:
                return (
                    f"Error: No se encontró el curso '{course_id}' "
                    "o falta la relación con CourseBase."
                )

            base_course = meta["base"]

            # 2. Sentiment counts
            stats = session.run(
                "MATCH (ce:Concept:CourseEdition {prefLabel: $cid})"
                "<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment) "
                "RETURN c.sentiment as sentiment, count(*) as count",
                cid=course_id,
            )
            sentiment_counts = {r["sentiment"]: r["count"] for r in stats}
            total = sum(sentiment_counts.values())

            if total == 0:
                return f"El curso '{course_id}' existe pero no tiene comentarios registrados."

            # 3. Top negative aspects
            neg = session.run(
                "MATCH (ce:Concept:CourseEdition {prefLabel: $cid})"
                "<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment) "
                "MATCH (c)-[r:MENTIONS]->(a:Concept:Aspect) "
                "WHERE r.sentiment = 'Negativo' "
                "RETURN a.prefLabel as aspect, count(*) as count "
                "ORDER BY count DESC LIMIT 5",
                cid=course_id,
            )
            neg_aspects = [f"{r['aspect']} ({r['count']})" for r in neg]

            # 4. Top positive aspects
            pos = session.run(
                "MATCH (ce:Concept:CourseEdition {prefLabel: $cid})"
                "<-[:BROADER]-(t:Concept:Thread)<-[:BROADER]-(c:Concept:Comment) "
                "MATCH (c)-[r:MENTIONS]->(a:Concept:Aspect) "
                "WHERE r.sentiment = 'Positivo' "
                "RETURN a.prefLabel as aspect, count(*) as count "
                "ORDER BY count DESC LIMIT 5",
                cid=course_id,
            )
            pos_aspects = [f"{r['aspect']} ({r['count']})" for r in pos]

        # LLM synthesis
        prompt = (
            f'Genera un reporte ejecutivo breve para el curso "{course_id}" '
            f"(Base: {base_course}).\n\n"
            f"DATOS:\n"
            f"- Total Comentarios: {total}\n"
            f"- Sentimientos: {sentiment_counts}\n"
            f"- Principales Quejas (Top 5): {', '.join(neg_aspects) or 'Ninguna'}\n"
            f"- Principales Fortalezas (Top 5): {', '.join(pos_aspects) or 'Ninguna'}\n\n"
            "Estructura el reporte en:\n"
            "1. Resumen General\n"
            "2. Puntos Críticos (Quejas)\n"
            "3. Aciertos (Fortalezas)\n"
            "4. Recomendación breve"
        )

        response = self.llm.complete(prompt)
        return str(response)
