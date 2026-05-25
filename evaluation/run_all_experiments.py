#!/usr/bin/env python3
"""
Master experiment orchestrator — runs Phases A → B → C in order.

This script implements Phase 5 (Evaluation) of the DSR methodology
(Peffers et al., 2007) for the hybrid ABSA artifact.

Execution order:
  1. export_neo4j_sample.py  → data/sample_700_labeled.csv + embeddings
  2. Phase A baselines       → evaluation/results/baselines.json
  3. Phase B inference (5×)  → evaluation/results/{model}.jsonl
  4. Phase C judge (5×)      → evaluation/results/{model}_judged.jsonl
  5. compute_metrics.py      → evaluation/results/comparative_table.csv/.json

Usage:
    python -m evaluation.run_all_experiments
    python -m evaluation.run_all_experiments --dry-run
    python -m evaluation.run_all_experiments --skip-export --skip-baselines
    python -m evaluation.run_all_experiments --models gpt-4o-mini gpt-4o
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_all_experiments")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
EMBEDDINGS_NPZ = PROJECT_ROOT / "data" / "sample_700_embeddings.npz"
ASPECT_VECTORS = PROJECT_ROOT / "data" / "aspect_vectors.json"
ONTOLOGY_JSON = PROJECT_ROOT / "data" / "exports" / "ontology_aspects.json"

# All Phase B models
ALL_MODELS = [
    "gpt-4o-mini", "gpt-4o",
    "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
]


# ---------------------------------------------------------------------------
# Dry-run — FIX #5: real connectivity checks
# ---------------------------------------------------------------------------


def run_dry_run() -> None:
    """Validate all connections and data files without making inference calls."""
    load_dotenv(PROJECT_ROOT / ".env")
    errors: List[str] = []

    # 1. Neo4j connectivity
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        database = os.getenv("NEO4J_DATABASE", None)
        driver = GraphDatabase.driver(uri, auth=(user, password))
        session_kwargs = {"database": database} if database else {}
        with driver.session(**session_kwargs) as session:
            session.run("RETURN 1").single()
        driver.close()
        logger.info("✓ Neo4j reachable at %s", uri)
    except Exception as exc:
        errors.append(f"Neo4j: {exc}")
        logger.error("✗ Neo4j connection failed: %s", exc)

    # 2. OpenAI API key
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key)
        client.models.list()
        logger.info("✓ OpenAI API key valid")
    except Exception as exc:
        errors.append(f"OpenAI: {exc}")
        logger.error("✗ OpenAI API check failed: %s", exc)

    # 3. Google API key
    try:
        import google.generativeai as genai
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            raise ValueError("GOOGLE_API_KEY not set")
        genai.configure(api_key=google_key)
        list(genai.list_models())
        logger.info("✓ Google API key valid")
    except Exception as exc:
        errors.append(f"Google: {exc}")
        logger.error("✗ Google API check failed: %s", exc)

    # 4. Data files
    for fp in [SAMPLE_CSV, EMBEDDINGS_NPZ, ASPECT_VECTORS, ONTOLOGY_JSON]:
        if fp.exists():
            logger.info("✓ Data file present: %s", fp.name)
        else:
            msg = f"Data file missing: {fp}"
            errors.append(msg)
            logger.warning("⚠ %s (will be created during export)", msg)

    # Summary
    print()
    if errors:
        logger.warning("Dry run completed with %d issues:", len(errors))
        for e in errors:
            logger.warning("  - %s", e)
    else:
        logger.info("✓ Dry run complete — all connections OK.")

    sys.exit(1 if errors else 0)


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


def step_1_export(force: bool = False) -> None:
    """Step 1: Export sample from Neo4j + compute embeddings."""
    logger.info("=" * 60)
    logger.info("STEP 1 — Data Export")
    logger.info("=" * 60)

    from evaluation.data_export.export_neo4j_sample import (
        export_sample_from_neo4j,
        precompute_comment_embeddings,
        precompute_aspect_vectors,
    )

    df = export_sample_from_neo4j(force=force)
    precompute_comment_embeddings(df, force=force)
    precompute_aspect_vectors(force=force)
    logger.info("✓ Step 1 complete.\n")


def step_2_baselines() -> None:
    """Step 2: Run all Phase A baselines."""
    logger.info("=" * 60)
    logger.info("STEP 2 — Phase A: Baselines")
    logger.info("=" * 60)

    import pandas as pd
    import numpy as np

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SAMPLE_CSV)

    # A1: Majority class
    logger.info("--- A1: Majority class ---")
    from evaluation.baselines.baseline_majority_class import run_majority_baseline
    majority_results = run_majority_baseline(df)
    _save_baseline("baseline_majority_class", majority_results)

    # A2: Cosine + keyword sentiment
    logger.info("--- A2: Cosine + keyword sentiment ---")
    from evaluation.baselines.baseline_cosine_only import run_cosine_baseline
    emb_data = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    with open(ASPECT_VECTORS, "r", encoding="utf-8") as fh:
        aspect_vectors = json.load(fh)
    cosine_results = run_cosine_baseline(
        df, emb_data["embeddings"], list(emb_data["ids"]), aspect_vectors
    )
    _save_baseline("baseline_cosine_only", cosine_results)

    # A3: No guides (requires API)
    logger.info("--- A3: No guides ablation ---")
    from evaluation.baselines.baseline_no_guides import run_no_guides_baseline
    with open(ONTOLOGY_JSON, "r", encoding="utf-8") as fh:
        ontologia = json.load(fh)["ontologia_aspectos"]
    out_path = RESULTS_DIR / "baseline_no_guides.json"
    run_no_guides_baseline(df, ontologia, out_path)

    logger.info("✓ Step 2 complete.\n")


def _save_baseline(name: str, results: list) -> None:
    """Save baseline results to JSON."""
    path = RESULTS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    logger.info("  Saved %d records → %s", len(results), path)


def step_3_inference(models: List[str]) -> None:
    """Step 3: Run Phase B inference for specified models."""
    logger.info("=" * 60)
    logger.info("STEP 3 — Phase B: Multi-LLM Inference")
    logger.info("=" * 60)

    import numpy as np
    import pandas as pd
    from evaluation.multi_llm.inference_runner import (
        run_inference,
        validate_model_names,
    )

    validate_model_names()

    df = pd.read_csv(SAMPLE_CSV)
    emb_data = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    embeddings = emb_data["embeddings"]
    emb_ids = list(emb_data["ids"])

    with open(ASPECT_VECTORS, "r", encoding="utf-8") as fh:
        aspect_vectors = json.load(fh)
    with open(ONTOLOGY_JSON, "r", encoding="utf-8") as fh:
        ontologia = json.load(fh)["ontologia_aspectos"]

    for model_key in models:
        logger.info("--- Inference: %s ---", model_key)
        run_inference(model_key, df, embeddings, emb_ids, aspect_vectors, ontologia)

    logger.info("✓ Step 3 complete.\n")


def step_4_judge(models: List[str]) -> None:
    """Step 4: Run Phase C judge on all Phase B outputs."""
    logger.info("=" * 60)
    logger.info("STEP 4 — Phase C: LLM-as-a-Judge (GPT-4o)")
    logger.info("=" * 60)

    from openai import OpenAI
    from evaluation.multi_llm.judge_evaluator import evaluate_model

    load_dotenv(PROJECT_ROOT / ".env")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    for model_key in models:
        logger.info("--- Judging: %s ---", model_key)
        evaluate_model(model_key, client)

    logger.info("✓ Step 4 complete.\n")


def step_5_metrics() -> None:
    """Step 5: Compute and save comparative metrics."""
    logger.info("=" * 60)
    logger.info("STEP 5 — Compute Metrics")
    logger.info("=" * 60)

    from evaluation.metrics.compute_metrics import compute_all_metrics

    df = compute_all_metrics()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = RESULTS_DIR / "comparative_table.csv"
    df.to_csv(csv_path, index=False)

    json_path = RESULTS_DIR / "comparative_table.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(df.to_dict(orient="records"), fh, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("COMPARATIVE TABLE — FINAL RESULTS")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80 + "\n")

    logger.info("✓ Step 5 complete. Results → %s\n", RESULTS_DIR)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Master experiment orchestrator — "
            "DSR Phase 5 (Evaluation) for the hybrid ABSA artifact."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate connectivity and data files without running experiments.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip Step 1 (data export from Neo4j).",
    )
    parser.add_argument(
        "--skip-baselines",
        action="store_true",
        help="Skip Step 2 (Phase A baselines).",
    )
    parser.add_argument(
        "--skip-inference",
        action="store_true",
        help="Skip Step 3 (Phase B inference).",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip Step 4 (Phase C judge).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=ALL_MODELS,
        default=ALL_MODELS,
        help="Subset of models to run (default: all).",
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="Force re-export from Neo4j even if CSV exists.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()

    if args.dry_run:
        run_dry_run()
        return

    logger.info("=" * 80)
    logger.info("MULTI-LLM ABSA EXPERIMENT PIPELINE")
    logger.info("Models: %s", args.models)
    logger.info("=" * 80 + "\n")

    if not args.skip_export:
        step_1_export(force=args.force_export)

    if not args.skip_baselines:
        step_2_baselines()

    if not args.skip_inference:
        step_3_inference(args.models)

    if not args.skip_judge:
        step_4_judge(args.models)

    step_5_metrics()

    logger.info("🎉 All experiments complete!")


if __name__ == "__main__":
    main()
