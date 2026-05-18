"""
Analytics app configuration.

The ready() method initializes the Neo4j and RAG singletons once
when Django starts. An atexit handler ensures clean driver shutdown.
"""

import atexit
import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger('analytics')


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'TIC ABSA Analytics'

    def ready(self):
        """Initialize service singletons at startup."""
        from .services.neo4j_service import Neo4jService
        from .services.rag_service import RAGService

        # --- Neo4j ---
        neo4j_svc = Neo4jService()
        try:
            neo4j_svc.initialize(
                uri=settings.NEO4J_URI,
                user=settings.NEO4J_USER,
                password=settings.NEO4J_PASSWORD,
                database=settings.NEO4J_DATABASE,
            )
        except Exception as e:
            logger.error("Failed to connect to Neo4j: %s", e)
            logger.warning(
                "The dashboard will show connection errors until Neo4j is available."
            )

        # --- RAG ---
        rag_svc = RAGService()
        try:
            rag_svc.initialize(openai_api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            logger.error("Failed to initialize RAG engine: %s", e)

        # --- Cleanup on shutdown ---
        def _shutdown():
            logger.info("Shutting down analytics services...")
            neo4j_svc.close()

        atexit.register(_shutdown)
