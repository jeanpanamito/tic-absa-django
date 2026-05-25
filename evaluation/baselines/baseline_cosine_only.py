#!/usr/bin/env python3
"""
Baseline A2 — Cosine-similarity + keyword sentiment (no LLM).

For each comment:
  1. Loads its pre-computed embedding from sample_700_embeddings.npz.
  2. Computes cosine similarity against the 9 SKOS aspect vectors.
  3. Assigns the max-similarity aspect.
  4. Assigns sentiment via a Spanish keyword lexicon (no LLM call).

This isolates the contribution of vector similarity alone from the
full hybrid pipeline.

Usage:
    python -m evaluation.baselines.baseline_cosine_only
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("baseline_cosine")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
EMBEDDINGS_NPZ = PROJECT_ROOT / "data" / "sample_700_embeddings.npz"
ASPECT_VECTORS_JSON = PROJECT_ROOT / "data" / "aspect_vectors.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


# ---------------------------------------------------------------------------
# Keyword sentiment lexicon (Spanish, educational domain)
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS: List[str] = [
    "excelente", "bueno", "buena", "bien", "gustó", "gusto",
    "aprendí", "aprendi", "recomiendo", "perfecto", "perfecta",
    "claro", "clara", "útil", "util", "interesante",
    "gracias", "genial", "contenta", "contento", "maravilloso",
    "fantástico", "fantastico", "fabuloso", "agradezco",
    "satisfecho", "satisfecha", "encanta", "feliz",
]

NEGATIVE_KEYWORDS: List[str] = [
    "malo", "mala", "difícil", "dificil", "confuso", "confusa",
    "no entendí", "no entendi", "mejorar", "problema", "problemas",
    "error", "errores", "no funciona", "aburrido", "aburrida",
    "no pude", "no puedo", "cerrada", "cerrado", "cuelga",
    "falta", "fallo", "falló", "complicado", "complicada",
    "frustrante", "imposible", "no sirve", "lento", "lenta",
]


def keyword_sentiment(text: str) -> str:
    """Classify sentiment using keyword matching (no LLM).

    Args:
        text: Comment text.

    Returns:
        ``"Positivo"``, ``"Negativo"``, or ``"Neutral"``.
    """
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_KEYWORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_KEYWORDS if w in text_lower)
    if pos > neg:
        return "Positivo"
    if neg > pos:
        return "Negativo"
    return "Neutral"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _normalize(v: np.ndarray) -> np.ndarray:
    """L2-normalize a vector (or return zeros if norm ≈ 0)."""
    norm = np.linalg.norm(v)
    if norm < 1e-12:
        return v
    return v / norm


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two L2-normalized vectors."""
    return float(np.clip(np.dot(_normalize(a), _normalize(b)), -1.0, 1.0))


def run_cosine_baseline(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    emb_ids: List[str],
    aspect_vectors: Dict[str, List[float]],
) -> List[Dict[str, Any]]:
    """Run cosine-similarity + keyword-sentiment baseline.

    Args:
        df: The 700-triple sample.
        embeddings: Pre-computed comment embeddings (N_unique × 1536).
        emb_ids: Comment IDs corresponding to ``embeddings`` rows.
        aspect_vectors: Dict mapping aspect name → 1536-d vector.

    Returns:
        List of per-row result dicts in unified Phase B schema.
    """
    # Build lookup: comment_id → embedding index
    id_to_idx: Dict[str, int] = {cid: i for i, cid in enumerate(emb_ids)}

    # Pre-convert aspect vectors to numpy
    aspect_names = list(aspect_vectors.keys())
    aspect_matrix = np.array(
        [aspect_vectors[name] for name in aspect_names], dtype=np.float32
    )

    results: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        cid = str(row["comment_id"])
        text = str(row.get("comment_text", ""))

        idx = id_to_idx.get(cid)
        if idx is None:
            # Fallback: no embedding found
            pred_aspect = "General"
            max_sim = 0.0
        else:
            comment_emb = embeddings[idx]
            sims = np.array([
                _cosine_similarity(comment_emb, aspect_matrix[i])
                for i in range(len(aspect_names))
            ])
            best_idx = int(np.argmax(sims))
            pred_aspect = aspect_names[best_idx]
            max_sim = float(sims[best_idx])

        pred_sentiment = keyword_sentiment(text)

        results.append({
            "comment_id": cid,
            "comment_text": text,
            "model": "cosine_only",
            "predicted_aspects": [
                {
                    "aspecto_oficial": pred_aspect,
                    "sentimiento": pred_sentiment,
                    "confianza": round(max_sim, 4),
                    "mencion_original": "",
                    "justificacion": f"Max cosine similarity = {max_sim:.4f}; "
                                     f"keyword sentiment = {pred_sentiment}",
                }
            ],
            "raw_response": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_s": 0.0,
            "json_parse_error": False,
            "timestamp": "",
        })

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Baseline A2 — cosine similarity + keyword sentiment.",
    )
    parser.add_argument(
        "--input", type=str, default=str(SAMPLE_CSV),
        help="Path to the 700-comment sample CSV.",
    )
    parser.add_argument(
        "--output-dir", type=str, default=str(RESULTS_DIR),
        help="Directory to write results.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        logger.error("Sample CSV not found at %s", csv_path)
        return

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    # Load pre-computed embeddings
    if not EMBEDDINGS_NPZ.exists():
        logger.error("Embeddings not found at %s", EMBEDDINGS_NPZ)
        logger.error("Run export_neo4j_sample.py first.")
        return

    emb_data = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    embeddings = emb_data["embeddings"]
    emb_ids = list(emb_data["ids"])
    logger.info("Loaded %d embeddings from %s", len(emb_ids), EMBEDDINGS_NPZ)

    # Load aspect vectors
    if not ASPECT_VECTORS_JSON.exists():
        logger.error("Aspect vectors not found at %s", ASPECT_VECTORS_JSON)
        return

    with open(ASPECT_VECTORS_JSON, "r", encoding="utf-8") as fh:
        aspect_vectors = json.load(fh)
    logger.info("Loaded %d aspect vectors.", len(aspect_vectors))

    results = run_cosine_baseline(df, embeddings, emb_ids, aspect_vectors)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline_cosine_only.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

    logger.info("✓ Cosine baseline → %s (%d rows)", out_path, len(results))


if __name__ == "__main__":
    main()
