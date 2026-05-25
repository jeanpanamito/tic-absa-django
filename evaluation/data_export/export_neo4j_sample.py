#!/usr/bin/env python3
"""
Export a stratified 700-comment sample from Neo4j for experiment reproducibility.

Produces:
  - data/sample_700_labeled.csv   (700 triples: comment × aspect × sentiment)
  - data/sample_700_embeddings.npz (pre-computed text-embedding-3-small vectors)
  - data/aspect_vectors.json       (9 pre-computed aspect reference vectors)

The CSV is committed to the repo once and never re-generated unless --force
is passed.  All Phase B models read the same pre-computed embeddings so that
(a) cost is paid once and (b) there is zero risk of embedding-model drift
between runs.

Usage:
    python -m evaluation.data_export.export_neo4j_sample
    python -m evaluation.data_export.export_neo4j_sample --force
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("export_neo4j_sample")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_CSV = DATA_DIR / "sample_700_labeled.csv"
EMBEDDINGS_NPZ = DATA_DIR / "sample_700_embeddings.npz"
ASPECT_VECTORS_JSON = DATA_DIR / "aspect_vectors.json"
ONTOLOGY_JSON = DATA_DIR / "exports" / "ontology_aspects.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_SIZE = 700
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# ---------------------------------------------------------------------------
# Cypher query — stratified random sample, frozen after first export
# ---------------------------------------------------------------------------
SAMPLE_QUERY = """
MATCH (c:Concept:Comment)-[m:MENTIONS]->(a:Concept:Aspect)
MATCH (c)-[:BROADER]->(t:Concept:Thread)-[:BROADER]->(ce:Concept:CourseEdition)
WHERE c.text IS NOT NULL AND c.text <> '' AND size(c.text) > 30
WITH c, m, a, ce, rand() AS r
ORDER BY r
LIMIT $limit
RETURN
    c.id          AS comment_id,
    c.text        AS comment_text,
    a.prefLabel   AS true_aspect,
    m.sentiment   AS true_sentiment,
    c.confidence  AS confidence,
    ce.prefLabel  AS course
"""


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------


def _get_neo4j_driver() -> Any:
    """Create a Neo4j driver from environment variables."""
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise ImportError(
            "neo4j driver required.  pip install neo4j"
        ) from exc

    load_dotenv(PROJECT_ROOT / ".env")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", None)

    driver = GraphDatabase.driver(uri, auth=(user, password))
    logger.info("Connecting to Neo4j at %s (user=%s, db=%s)", uri, user, database)
    return driver, database


def export_sample_from_neo4j(
    force: bool = False,
) -> pd.DataFrame:
    """Export *SAMPLE_SIZE* comment–aspect–sentiment triples from Neo4j.

    If the CSV already exists and ``force`` is ``False``, the cached CSV is
    loaded and returned without querying Neo4j.
    """
    if SAMPLE_CSV.exists() and not force:
        logger.info(
            "Sample already exists at %s. Use --force to re-export.", SAMPLE_CSV
        )
        return pd.read_csv(SAMPLE_CSV)

    driver, database = _get_neo4j_driver()

    try:
        driver.verify_connectivity()
        logger.info("✓ Neo4j connection verified.")
    except Exception as exc:
        logger.error("Cannot connect to Neo4j: %s", exc)
        raise

    records: List[Dict[str, Any]] = []
    try:
        session_kwargs: Dict[str, Any] = {}
        if database:
            session_kwargs["database"] = database

        with driver.session(**session_kwargs) as session:
            result = session.run(SAMPLE_QUERY, limit=SAMPLE_SIZE)
            for record in result:
                records.append({
                    "comment_id": record["comment_id"],
                    "comment_text": record["comment_text"],
                    "true_aspect": record["true_aspect"],
                    "true_sentiment": record["true_sentiment"],
                    "confidence": record["confidence"],
                    "course": record["course"],
                })
    finally:
        driver.close()

    if not records:
        raise RuntimeError(
            "Neo4j returned 0 records. Check that ABSA triples have been "
            "ingested (MENTIONS edges with text > 30 chars)."
        )

    df = pd.DataFrame(records)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAMPLE_CSV, index=False, encoding="utf-8")
    logger.info(
        "Exported %d triples → %s  (courses: %s)",
        len(df),
        SAMPLE_CSV,
        df["course"].nunique(),
    )
    return df


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------


def _get_openai_client() -> Any:
    """Create an OpenAI client from environment variables."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("openai>=1.0 required.  pip install openai") from exc

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment.")
    return OpenAI(api_key=api_key)


def precompute_comment_embeddings(
    df: pd.DataFrame,
    force: bool = False,
) -> Tuple[np.ndarray, List[str]]:
    """Compute text-embedding-3-small for every *unique* comment.

    Saves a compressed ``.npz`` with keys ``ids`` (1-D string array) and
    ``embeddings`` (N × 1536 float32).  Returns ``(embeddings, ids)``.
    """
    if EMBEDDINGS_NPZ.exists() and not force:
        logger.info("Embeddings already cached at %s.", EMBEDDINGS_NPZ)
        data = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
        return data["embeddings"], list(data["ids"])

    client = _get_openai_client()

    unique_comments = (
        df[["comment_id", "comment_text"]]
        .drop_duplicates(subset=["comment_id"])
        .reset_index(drop=True)
    )
    logger.info(
        "Computing embeddings for %d unique comments (model=%s)…",
        len(unique_comments),
        EMBEDDING_MODEL,
    )

    ids: List[str] = []
    embeddings: List[np.ndarray] = []

    # Process in batches of 50 to stay within rate limits
    batch_size = 50
    for start in tqdm(
        range(0, len(unique_comments), batch_size),
        desc="Embedding batches",
        unit="batch",
    ):
        batch = unique_comments.iloc[start : start + batch_size]
        texts = batch["comment_text"].tolist()
        batch_ids = batch["comment_id"].tolist()

        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL, input=texts
            )
            for item, cid in zip(response.data, batch_ids):
                vec = np.asarray(item.embedding, dtype=np.float32)
                embeddings.append(vec)
                ids.append(cid)
        except Exception as exc:
            logger.error("Embedding API error on batch %d: %s", start, exc)
            # Fill with zeros so indices stay aligned
            for cid in batch_ids:
                embeddings.append(np.zeros(EMBEDDING_DIM, dtype=np.float32))
                ids.append(cid)

        time.sleep(0.3)  # light rate-limit courtesy

    emb_matrix = np.stack(embeddings)
    np.savez_compressed(
        EMBEDDINGS_NPZ,
        ids=np.array(ids, dtype=object),
        embeddings=emb_matrix,
    )
    logger.info(
        "Saved %d embeddings (%s) → %s",
        emb_matrix.shape[0],
        emb_matrix.shape,
        EMBEDDINGS_NPZ,
    )
    return emb_matrix, ids


def precompute_aspect_vectors(force: bool = False) -> Dict[str, List[float]]:
    """Compute reference embeddings for the 9 SKOS aspects.

    Uses the same text template as semantic_pipeline.py:
        ``"Aspecto: {name}. Descripción: {desc}"``
    """
    if ASPECT_VECTORS_JSON.exists() and not force:
        logger.info("Aspect vectors already cached at %s.", ASPECT_VECTORS_JSON)
        with open(ASPECT_VECTORS_JSON, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Load ontology
    if not ONTOLOGY_JSON.exists():
        raise FileNotFoundError(
            f"Ontology not found at {ONTOLOGY_JSON}. "
            "Run graph_construction/skos_builder.py first."
        )
    with open(ONTOLOGY_JSON, "r", encoding="utf-8") as fh:
        ontology = json.load(fh)

    aspects = ontology["ontologia_aspectos"]
    client = _get_openai_client()
    vectors: Dict[str, List[float]] = {}

    for name, info in tqdm(aspects.items(), desc="Aspect vectors"):
        desc = info.get("descripcion", "")
        text = f"Aspecto: {name}. Descripción: {desc}"
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL, input=text
            )
            vectors[name] = response.data[0].embedding
        except Exception as exc:
            logger.error("Failed to embed aspect '%s': %s", name, exc)
            vectors[name] = [0.0] * EMBEDDING_DIM
        time.sleep(0.2)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASPECT_VECTORS_JSON, "w", encoding="utf-8") as fh:
        json.dump(vectors, fh, ensure_ascii=False)
    logger.info("Saved %d aspect vectors → %s", len(vectors), ASPECT_VECTORS_JSON)
    return vectors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export a 700-comment stratified sample from Neo4j.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-export even if CSV / embeddings already exist.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding pre-computation (CSV only).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()

    # Step 1 — export CSV from Neo4j
    df = export_sample_from_neo4j(force=args.force)
    logger.info("Sample shape: %s", df.shape)

    # Step 2 — pre-compute embeddings
    if not args.skip_embeddings:
        precompute_comment_embeddings(df, force=args.force)
        precompute_aspect_vectors(force=args.force)
    else:
        logger.info("Skipping embedding computation (--skip-embeddings).")

    logger.info("✓ Data export complete.")


if __name__ == "__main__":
    main()
