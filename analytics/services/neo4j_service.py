"""
Neo4j Service — Thread-safe singleton for Neo4j operations.

Adapted from the original neo4j_dashboard.py (Streamlit connector).
Uses a single Neo4j driver instance with built-in connection pooling.

The driver is initialized once at Django startup via AppConfig.ready()
and reused across all request threads. Each method opens an ephemeral
session via `with self.driver.session()` which is safe for concurrent use.
"""

import logging
import threading
from typing import Dict, List, Any, Optional

from neo4j import GraphDatabase

logger = logging.getLogger('analytics.neo4j')


class Neo4jService:
    """
    Singleton service wrapping all Neo4j/Cypher operations.

    The Neo4j Python driver manages its own internal connection pool,
    so a single driver instance is shared across threads. Each public
    method opens a short-lived session, executes queries, and returns
    plain Python data structures (dicts/lists) ready for JSON serialization.
    """

    _instance: Optional['Neo4jService'] = None
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

    def initialize(self, uri: str, user: str, password: str, database: str = 'neo4j') -> None:
        """Initialize the Neo4j driver (called once from AppConfig.ready)."""
        if self._initialized:
            return
        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        self.driver.verify_connectivity()
        self.database = database
        self._initialized = True
        logger.info("Neo4j driver initialized — pool connected to %s", uri)

    def close(self) -> None:
        """Shut down the driver pool gracefully."""
        if self._initialized and hasattr(self, 'driver'):
            self.driver.close()
            self._initialized = False
            logger.info("Neo4j driver closed.")

    @property
    def is_connected(self) -> bool:
        return self._initialized

    # ──────────────────────────────────────────────
    # Overview / KPI queries
    # ──────────────────────────────────────────────

    def get_general_statistics(self) -> Dict[str, Any]:
        """Return high-level KPIs for the overview dashboard."""
        with self.driver.session(database=self.database) as session:
            total_comments = session.run(
                "MATCH (c:Concept:Comment) RETURN count(c) as count"
            ).single()["count"]

            total_mentions = session.run(
                "MATCH ()-[r:MENTIONS]->() RETURN count(r) as count"
            ).single()["count"]

            total_aspects = session.run(
                "MATCH (a:Concept:Aspect) RETURN count(a) as count"
            ).single()["count"]

            avg_confidence = session.run(
                "MATCH (c:Concept:Comment) RETURN avg(c.confidence) as avg"
            ).single()["avg"] or 0.0

            total_courses = session.run(
                "MATCH (ce:Concept:CourseEdition) RETURN count(ce) as count"
            ).single()["count"]

            total_threads = session.run(
                "MATCH (t:Concept:Thread) RETURN count(t) as count"
            ).single()["count"]

            return {
                "total_comments": total_comments,
                "total_mentions": total_mentions,
                "total_aspects": total_aspects,
                "avg_confidence": round(avg_confidence, 4),
                "total_courses": total_courses,
                "total_threads": total_threads,
            }

    # ──────────────────────────────────────────────
    # Distribution queries
    # ──────────────────────────────────────────────

    def get_polarity_distribution(self) -> List[Dict]:
        """Polarity counts (for donut / pie chart)."""
        query = """
        MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
        RETURN r.sentiment as polarity, count(*) as count
        ORDER BY count DESC
        """
        with self.driver.session(database=self.database) as session:
            return [
                {"polarity": r["polarity"], "count": r["count"]}
                for r in session.run(query)
            ]

    def get_aspect_distribution(self) -> List[Dict]:
        """Mention counts per aspect (for horizontal bar chart)."""
        query = """
        MATCH (c:Concept:Comment)-[:MENTIONS]->(a:Concept:Aspect)
        RETURN a.prefLabel as aspect, count(*) as count
        ORDER BY count DESC
        """
        with self.driver.session(database=self.database) as session:
            return [
                {"aspect": r["aspect"], "count": r["count"]}
                for r in session.run(query)
            ]

    def get_sentiment_heatmap(self) -> List[Dict]:
        """Aspect × Sentiment matrix (for heatmap)."""
        query = """
        MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
        RETURN a.prefLabel as aspect, r.sentiment as sentiment, count(*) as count
        ORDER BY aspect, sentiment
        """
        with self.driver.session(database=self.database) as session:
            return [
                {"aspect": r["aspect"], "sentiment": r["sentiment"], "count": r["count"]}
                for r in session.run(query)
            ]

    # ──────────────────────────────────────────────
    # Detailed analysis queries
    # ──────────────────────────────────────────────

    def get_top_negative_aspects(self, limit: int = 10) -> List[Dict]:
        """Aspects with most negative mentions."""
        query = """
        MATCH (c:Concept:Comment)-[r:MENTIONS {sentiment: 'Negativo'}]->(a:Concept:Aspect)
        RETURN a.prefLabel as aspect, count(*) as count
        ORDER BY count DESC
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            return [
                {"aspect": r["aspect"], "count": r["count"]}
                for r in session.run(query, limit=limit)
            ]

    def get_course_sentiment_ranking(self) -> List[Dict]:
        """Course ranking by negative ratio (Comment → Thread → CourseEdition)."""
        query = """
        MATCH (c:Concept:Comment)-[:BROADER]->(t:Concept:Thread)-[:BROADER]->(ce:Concept:CourseEdition)
        MATCH (c)-[r:MENTIONS]->(a:Concept:Aspect)
        WITH ce.prefLabel as course, r.sentiment as sentiment, count(*) as count
        ORDER BY course, sentiment
        RETURN course, sentiment, count
        """
        with self.driver.session(database=self.database) as session:
            data = [
                {"course": r["course"], "sentiment": r["sentiment"], "count": r["count"]}
                for r in session.run(query)
            ]

        # Aggregate in Python for ratio calculation
        courses: Dict[str, Dict[str, int]] = {}
        for row in data:
            cid = row["course"]
            if cid not in courses:
                courses[cid] = {"Positivo": 0, "Negativo": 0, "Neutral": 0}
            courses[cid][row["sentiment"]] += row["count"]

        result = []
        for cid, counts in courses.items():
            total = sum(counts.values())
            if total > 0:
                result.append({
                    "course": cid,
                    "positivos": counts["Positivo"],
                    "negativos": counts["Negativo"],
                    "neutrales": counts["Neutral"],
                    "total": total,
                    "ratio_negativo": round(counts["Negativo"] / total, 4),
                })

        return sorted(result, key=lambda x: x["ratio_negativo"], reverse=True)

    def get_confidence_distribution(self) -> List[float]:
        """List of confidence values for histogram."""
        query = """
        MATCH (c:Concept:Comment)
        WHERE c.confidence IS NOT NULL
        RETURN c.confidence as conf
        LIMIT 5000
        """
        with self.driver.session(database=self.database) as session:
            return [r["conf"] for r in session.run(query)]

    # ──────────────────────────────────────────────
    # Filter helpers
    # ──────────────────────────────────────────────

    def get_available_aspects(self) -> List[str]:
        """All aspect labels (sorted)."""
        query = "MATCH (a:Concept:Aspect) RETURN a.prefLabel as name ORDER BY name"
        with self.driver.session(database=self.database) as session:
            return [r["name"] for r in session.run(query)]

    def get_available_courses(self) -> List[str]:
        """All course edition labels (sorted)."""
        query = "MATCH (ce:Concept:CourseEdition) RETURN ce.prefLabel as id ORDER BY id"
        with self.driver.session(database=self.database) as session:
            return [r["id"] for r in session.run(query)]

    def get_filtered_comments(
        self,
        aspects: Optional[List[str]] = None,
        polarities: Optional[List[str]] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict]:
        """Return comments matching the given filters (max 1000)."""
        query = """
        MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
        WHERE c.confidence >= $min_conf
        """
        params: Dict[str, Any] = {"min_conf": min_confidence}

        if aspects:
            query += " AND a.prefLabel IN $aspects"
            params["aspects"] = aspects

        if polarities:
            query += " AND r.sentiment IN $polarities"
            params["polarities"] = polarities

        query += """
        RETURN
            c.id as id_comentario,
            c.text as text,
            a.prefLabel as aspecto,
            r.sentiment as sentimiento,
            c.confidence as confianza,
            c.justification as justificacion
        LIMIT 1000
        """
        with self.driver.session(database=self.database) as session:
            return [dict(r) for r in session.run(query, **params)]

    # ──────────────────────────────────────────────
    # Graph visualization data
    # ──────────────────────────────────────────────

    def get_graph_data(
        self, max_nodes: int = 100, focus_aspect: Optional[str] = None
    ) -> Dict[str, list]:
        """
        Return nodes + edges for Vis.js visualization.
        If focus_aspect is given, only return comments mentioning that aspect.
        """
        nodes: List[Dict] = []
        edges: List[Dict] = []
        node_ids: set = set()

        if focus_aspect:
            query = """
            MATCH (a:Concept:Aspect {prefLabel: $focus_aspect})
            MATCH (c:Concept:Comment)-[r:MENTIONS]->(a)
            WITH c, r, a
            LIMIT $limit
            RETURN c, r, a
            """
            params = {"limit": max_nodes, "focus_aspect": focus_aspect}
        else:
            query = """
            MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
            WITH c, r, a
            LIMIT $limit
            RETURN c, r, a
            """
            params = {"limit": max_nodes}

        with self.driver.session(database=self.database) as session:
            for record in session.run(query, **params):
                comment = record["c"]
                aspect = record["a"]
                rel = record["r"]

                c_label = comment.get("prefLabel") or f"Comment {str(comment.get('id', ''))[-4:]}"
                a_label = aspect.get("prefLabel") or "Aspect"

                c_id = f"C_{comment.element_id}"
                a_id = f"A_{a_label}"

                # Comment node
                if c_id not in node_ids:
                    nodes.append({
                        "id": c_id,
                        "label": c_label,
                        "group": "Comment",
                        "color": "#3b82f6",
                        "title": f"Text: {comment.get('text', '')[:120]}...",
                    })
                    node_ids.add(c_id)

                # Aspect node
                if a_id not in node_ids:
                    is_focused = focus_aspect and a_label == focus_aspect
                    nodes.append({
                        "id": a_id,
                        "label": a_label,
                        "group": "Aspect",
                        "color": "#f97316" if is_focused else "#10b981",
                        "title": f"Aspect: {a_label}",
                        "size": 40 if is_focused else 20,
                    })
                    node_ids.add(a_id)

                # Edge
                sentiment = rel["sentiment"]
                edge_color = (
                    "#ef4444" if sentiment == "Negativo"
                    else "#10b981" if sentiment == "Positivo"
                    else "#6b7280"
                )
                edges.append({
                    "from": c_id,
                    "to": a_id,
                    "label": sentiment,
                    "color": edge_color,
                })

        return {"nodes": nodes, "edges": edges}
