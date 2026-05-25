#!/usr/bin/env python3
"""
Baseline A1 — Majority-class classifier.

Assigns the most-frequent aspect and most-frequent sentiment from the
training distribution to every comment.  Uses sklearn DummyClassifier
for correct stratified metric computation.

Usage:
    python -m evaluation.baselines.baseline_majority_class
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sklearn.dummy import DummyClassifier

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("baseline_majority")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


def run_majority_baseline(
    df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Run majority-class baseline on both aspect and sentiment.

    Args:
        df: The 700-triple sample with columns
            ``true_aspect``, ``true_sentiment``.

    Returns:
        List of per-row result dicts in the unified Phase B schema.
    """
    # --- Aspect majority ---
    dummy_aspect = DummyClassifier(strategy="most_frequent")
    X_dummy = df.index.values.reshape(-1, 1)
    dummy_aspect.fit(X_dummy, df["true_aspect"])
    pred_aspects = dummy_aspect.predict(X_dummy)

    # --- Sentiment majority ---
    dummy_sent = DummyClassifier(strategy="most_frequent")
    dummy_sent.fit(X_dummy, df["true_sentiment"])
    pred_sentiments = dummy_sent.predict(X_dummy)

    majority_aspect = str(dummy_aspect.classes_[0]) if len(dummy_aspect.classes_) else "General"
    majority_sent = str(dummy_sent.classes_[0]) if len(dummy_sent.classes_) else "Neutral"
    logger.info(
        "Majority classes → aspect=%s, sentiment=%s", majority_aspect, majority_sent
    )

    results: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        results.append({
            "comment_id": row["comment_id"],
            "comment_text": row.get("comment_text", ""),
            "model": "majority_class",
            "predicted_aspects": [
                {
                    "aspecto_oficial": str(pred_aspects[idx]),
                    "sentimiento": str(pred_sentiments[idx]),
                    "confianza": 1.0,
                    "mencion_original": "",
                    "justificacion": "Majority class baseline",
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
        description="Baseline A1 — majority-class classifier.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(SAMPLE_CSV),
        help="Path to the 700-comment sample CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(RESULTS_DIR),
        help="Directory to write results.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        logger.error("Sample CSV not found at %s", csv_path)
        logger.error("Run export_neo4j_sample.py first.")
        return

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    results = run_majority_baseline(df)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline_majority_class.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

    logger.info("✓ Majority baseline → %s (%d rows)", out_path, len(results))


if __name__ == "__main__":
    main()
