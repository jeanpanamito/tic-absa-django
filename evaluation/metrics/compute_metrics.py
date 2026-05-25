#!/usr/bin/env python3
"""
Aggregate all Phase A–C results into the final comparative table.

Reads:
  - evaluation/results/baselines.json   (Phase A, combined)
  - evaluation/results/{model}.jsonl    (Phase B inference)
  - evaluation/results/{model}_judged.jsonl (Phase C judge verdicts)

Produces:
  - evaluation/results/comparative_table.csv
  - evaluation/results/comparative_table.json

Metrics per model:
  sent_f1_weighted, sent_f1_macro, aspect_acc, avg_confidence,
  latency_s, cost_usd, json_errors

Usage:
    python -m evaluation.metrics.compute_metrics
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sklearn.metrics import f1_score

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("compute_metrics")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

# Phase B model keys
LLM_MODEL_KEYS = [
    "gpt-4o-mini", "gpt-4o",
    "gemini-2.5-flash",
]

# Baseline keys (Phase A)
BASELINE_KEYS = [
    "baseline_majority_class",
    "baseline_cosine_only",
    "baseline_no_guides",
]

# ---------------------------------------------------------------------------
# Pricing table (USD per 1M tokens)
# ---------------------------------------------------------------------------

PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini":      {"input": 0.15,  "output": 0.60},
    "gpt-4o":           {"input": 2.50,  "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10,  "output": 0.40},
    "gemini-2.5-flash": {"input": 0.10,  "output": 0.40},
    "gemini-2.5-pro":   {"input": 1.25,  "output": 5.00},
    # Baselines — no cost
    "majority_class":       {"input": 0.0, "output": 0.0},
    "cosine_only":          {"input": 0.0, "output": 0.0},
    "no_guides_ablation":   {"input": 0.15, "output": 0.60},  # uses gpt-4o-mini
}


def _compute_cost(
    model_key: str,
    total_prompt_tokens: int,
    total_completion_tokens: int,
) -> float:
    """Compute total USD cost for a model run."""
    prices = PRICING.get(model_key, {"input": 0.0, "output": 0.0})
    cost_input = (total_prompt_tokens / 1_000_000) * prices["input"]
    cost_output = (total_completion_tokens / 1_000_000) * prices["output"]
    return round(cost_input + cost_output, 6)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))
    return records


def _load_json(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON file (list of dicts)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Metrics computation for a single model
# ---------------------------------------------------------------------------


def compute_model_metrics(
    model_key: str,
    inference_records: List[Dict[str, Any]],
    judge_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute all 7 metrics for a single model.

    Args:
        model_key: Model identifier.
        inference_records: Phase B output records.
        judge_records: Phase C judge verdicts.

    Returns:
        Dict with metric values.
    """
    n_total = len(judge_records) if judge_records else len(inference_records)

    if n_total == 0:
        logger.warning("No records for model %s", model_key)
        return {
            "model": model_key,
            "sent_f1_weighted": 0.0,
            "sent_f1_macro": 0.0,
            "aspect_acc": 0.0,
            "avg_confidence": 0.0,
            "latency_s": 0.0,
            "cost_usd": 0.0,
            "json_errors": 0.0,
        }

    # --- Sentiment F1 (from judge verdicts) ---
    y_pred: List[str] = []
    y_true: List[str] = []
    aspect_correct_count = 0

    for rec in judge_records:
        pred = str(rec.get("sentimiento_predicho", "Neutral")).strip().title()
        real = str(rec.get("sentimiento_real", "Neutral")).strip().title()
        if pred and real and real != "Error":
            y_pred.append(pred)
            y_true.append(real)
        if rec.get("aspecto_correcto", False):
            aspect_correct_count += 1

    labels = ["Positivo", "Negativo", "Neutral"]

    if y_pred and y_true:
        sent_f1_weighted = f1_score(
            y_true, y_pred, labels=labels, average="weighted", zero_division=0
        )
        sent_f1_macro = f1_score(
            y_true, y_pred, labels=labels, average="macro", zero_division=0
        )
    else:
        sent_f1_weighted = 0.0
        sent_f1_macro = 0.0

    # --- Aspect accuracy ---
    n_judged = len(judge_records) if judge_records else 1
    aspect_acc = aspect_correct_count / n_judged

    # --- Confidence (from inference records) ---
    confidences: List[float] = []
    for rec in inference_records:
        for asp in rec.get("predicted_aspects", []):
            conf = asp.get("confianza", 0.0)
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # --- Latency ---
    latencies = [
        rec.get("latency_s", 0.0)
        for rec in inference_records
        if isinstance(rec.get("latency_s"), (int, float))
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # --- Cost ---
    total_prompt = sum(rec.get("prompt_tokens", 0) for rec in inference_records)
    total_completion = sum(rec.get("completion_tokens", 0) for rec in inference_records)
    cost = _compute_cost(model_key, total_prompt, total_completion)

    # --- JSON errors ---
    json_error_count = sum(
        1 for rec in inference_records if rec.get("json_parse_error", False)
    )
    json_error_rate = json_error_count / len(inference_records) if inference_records else 0.0

    return {
        "model": model_key,
        "sent_f1_weighted": round(sent_f1_weighted, 4),
        "sent_f1_macro": round(sent_f1_macro, 4),
        "aspect_acc": round(aspect_acc, 4),
        "avg_confidence": round(avg_confidence, 4),
        "latency_s": round(avg_latency, 4),
        "cost_usd": cost,
        "json_errors": round(json_error_rate, 4),
    }


# ---------------------------------------------------------------------------
# Baseline metrics (no judge — compare against true labels)
# ---------------------------------------------------------------------------


def compute_baseline_metrics(
    baseline_key: str,
    baseline_records: List[Dict[str, Any]],
    sample_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Compute metrics for a baseline using true labels from the CSV.

    For baselines, we compare predictions against ``true_aspect`` and
    ``true_sentiment`` from the sample CSV rather than using the LLM judge.

    Args:
        baseline_key: Baseline file name (without extension).
        baseline_records: Loaded baseline results.
        sample_df: The 700-row sample with true labels.

    Returns:
        Dict with metric values.
    """
    if not baseline_records:
        return {
            "model": baseline_key,
            "sent_f1_weighted": 0.0, "sent_f1_macro": 0.0,
            "aspect_acc": 0.0, "avg_confidence": 0.0,
            "latency_s": 0.0, "cost_usd": 0.0, "json_errors": 0.0,
        }

    # Build lookup from true labels
    true_lookup: Dict[str, Dict[str, str]] = {}
    if sample_df is not None:
        for _, row in sample_df.iterrows():
            cid = str(row["comment_id"])
            true_lookup[cid] = {
                "aspect": str(row.get("true_aspect", "")),
                "sentiment": str(row.get("true_sentiment", "")),
            }

    y_pred_sent: List[str] = []
    y_true_sent: List[str] = []
    aspect_correct = 0
    confidences: List[float] = []
    total_prompt = 0
    total_completion = 0
    json_errors = 0

    for rec in baseline_records:
        cid = str(rec["comment_id"])
        true_data = true_lookup.get(cid, {})
        true_aspect = true_data.get("aspect", "")
        true_sentiment = true_data.get("sentiment", "Neutral")

        aspects = rec.get("predicted_aspects", [])
        if aspects:
            primary = aspects[0]
            pred_aspect = primary.get("aspecto_oficial", "")
            pred_sentiment = primary.get("sentimiento", "Neutral")
            conf = primary.get("confianza", 0.0)
        else:
            pred_aspect = ""
            pred_sentiment = "Neutral"
            conf = 0.0

        if pred_aspect == true_aspect:
            aspect_correct += 1

        y_pred_sent.append(pred_sentiment.title())
        y_true_sent.append(true_sentiment.title())
        confidences.append(float(conf))
        total_prompt += rec.get("prompt_tokens", 0)
        total_completion += rec.get("completion_tokens", 0)
        if rec.get("json_parse_error", False):
            json_errors += 1

    labels = ["Positivo", "Negativo", "Neutral"]
    n = len(baseline_records) or 1

    sent_f1_w = f1_score(y_true_sent, y_pred_sent, labels=labels,
                         average="weighted", zero_division=0) if y_pred_sent else 0.0
    sent_f1_m = f1_score(y_true_sent, y_pred_sent, labels=labels,
                         average="macro", zero_division=0) if y_pred_sent else 0.0

    # Determine internal model name for cost lookup
    internal_model = rec.get("model", baseline_key) if baseline_records else baseline_key
    cost = _compute_cost(internal_model, total_prompt, total_completion)

    latencies = [r.get("latency_s", 0.0) for r in baseline_records]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "model": baseline_key,
        "sent_f1_weighted": round(sent_f1_w, 4),
        "sent_f1_macro": round(sent_f1_m, 4),
        "aspect_acc": round(aspect_correct / n, 4),
        "avg_confidence": round(sum(confidences) / n, 4) if confidences else 0.0,
        "latency_s": round(avg_lat, 4),
        "cost_usd": cost,
        "json_errors": round(json_errors / n, 4),
    }


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------


def compute_all_metrics() -> pd.DataFrame:
    """Aggregate metrics for all baselines + LLM models.

    Returns:
        DataFrame with one row per model and 7 metric columns.
    """
    rows: List[Dict[str, Any]] = []

    # --- Load sample for baseline evaluation ---
    sample_csv = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
    sample_df = pd.read_csv(sample_csv) if sample_csv.exists() else None

    # --- Phase A: Baselines ---
    for bkey in BASELINE_KEYS:
        path = RESULTS_DIR / f"{bkey}.json"
        records = _load_json(path)
        if records:
            metrics = compute_baseline_metrics(bkey, records, sample_df)
            rows.append(metrics)
            logger.info("Baseline %s: %s", bkey, metrics)
        else:
            logger.warning("No baseline results found: %s", path)

    # --- Phase B+C: LLM models ---
    for model_key in LLM_MODEL_KEYS:
        inf_path = RESULTS_DIR / f"{model_key}.jsonl"
        judge_path = RESULTS_DIR / f"{model_key}_judged.jsonl"

        inf_records = _load_jsonl(inf_path)
        judge_records = _load_jsonl(judge_path)

        if inf_records or judge_records:
            metrics = compute_model_metrics(model_key, inf_records, judge_records)
            rows.append(metrics)
            logger.info("Model %s: %s", model_key, metrics)
        else:
            logger.warning("No results for model %s", model_key)

    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute comparative metrics from Phase A–C results.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(RESULTS_DIR),
        help="Directory to write comparative tables.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = compute_all_metrics()

    if df.empty:
        logger.error("No results to aggregate. Run experiments first.")
        return

    # CSV
    csv_path = out_dir / "comparative_table.csv"
    df.to_csv(csv_path, index=False)
    logger.info("✓ Comparative table (CSV) → %s", csv_path)

    # JSON
    json_path = out_dir / "comparative_table.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(df.to_dict(orient="records"), fh, ensure_ascii=False, indent=2)
    logger.info("✓ Comparative table (JSON) → %s", json_path)

    # Pretty print
    print("\n" + "=" * 80)
    print("COMPARATIVE TABLE")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
