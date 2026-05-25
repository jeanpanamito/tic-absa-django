#!/usr/bin/env python3
"""
Phase C — LLM-as-a-Judge evaluator (GPT-4o, fixed).

Evaluates ALL Phase B inference outputs using GPT-4o as a fixed judge.
Cross-provider judgment (GPT-4o judging Gemini outputs) partially
mitigates circular evaluation bias.

Output schema includes string labels for both predicted and real
sentiments, enabling sklearn F1 computation downstream.

Usage:
    python -m evaluation.multi_llm.judge_evaluator --model gpt-4o-mini
    python -m evaluation.multi_llm.judge_evaluator --all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("judge_evaluator")

# ---------------------------------------------------------------------------
# Paths & Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

JUDGE_MODEL = "gpt-4o"
TEMPERATURE = 0.0
DELAY_BETWEEN_CALLS = 0.5

# Models from inference_runner
MODEL_KEYS = [
    "gpt-4o-mini", "gpt-4o",
    "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-pro",
]

# ---------------------------------------------------------------------------
# Prompt import — single source of truth
# ---------------------------------------------------------------------------
from evaluation.prompts import JUDGE_SYSTEM_PROMPT, build_judge_user_prompt


# ---------------------------------------------------------------------------
# GPT-4o judge call
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_judge(
    client: Any,
    text: str,
    aspect: str,
    sentiment: str,
) -> Dict[str, Any]:
    """Call GPT-4o judge on a single ABSA prediction.

    Returns:
        Parsed JSON with keys:
        ``relevancia_aspecto``, ``aspecto_correcto``,
        ``sentimiento_correcto``, ``sentimiento_real``, ``explicacion``.
    """
    user_prompt = build_judge_user_prompt(text, aspect, sentiment)

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    return json.loads(content)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def evaluate_model(
    model_key: str,
    client: Any,
) -> List[Dict[str, Any]]:
    """Run GPT-4o judge on all Phase B outputs for a given model.

    Reads ``{model_key}.jsonl`` from results dir.
    Writes ``{model_key}_judged.jsonl`` incrementally.

    Args:
        model_key: The model whose outputs to judge.
        client: OpenAI client.

    Returns:
        List of judged result dicts.
    """
    inference_path = RESULTS_DIR / f"{model_key}.jsonl"
    if not inference_path.exists():
        logger.error("Inference results not found: %s", inference_path)
        return []

    # Load inference results
    inference_records: List[Dict[str, Any]] = []
    with open(inference_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                inference_records.append(json.loads(line))

    logger.info(
        "Loaded %d inference records for %s", len(inference_records), model_key
    )

    # Resume support
    judged_path = RESULTS_DIR / f"{model_key}_judged.jsonl"
    processed_ids: set[str] = set()
    results: List[Dict[str, Any]] = []

    if judged_path.exists():
        with open(judged_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    processed_ids.add(rec["comment_id"])
                    results.append(rec)
        logger.info("Resumed: %d already judged.", len(processed_ids))

    pending = [
        r for r in inference_records if r["comment_id"] not in processed_ids
    ]
    logger.info("Pending: %d records to judge.", len(pending))

    with open(judged_path, "a", encoding="utf-8") as fh:
        for record in tqdm(
            pending, desc=f"Judging [{model_key}]", unit="comment"
        ):
            cid = record["comment_id"]
            text = record["comment_text"]
            aspects = record.get("predicted_aspects", [])

            if not aspects:
                # No aspects predicted — write a placeholder
                judged = {
                    "comment_id": cid,
                    "model": model_key,
                    "aspecto_predicho": "",
                    "sentimiento_predicho": "",
                    "relevancia_aspecto": 0,
                    "aspecto_correcto": False,
                    "sentimiento_correcto": False,
                    "sentimiento_real": "",
                    "explicacion": "No aspects predicted by model.",
                }
                fh.write(json.dumps(judged, ensure_ascii=False) + "\n")
                fh.flush()
                results.append(judged)
                continue

            # Judge the FIRST predicted aspect (primary aspect)
            # If multi-aspect evaluation is needed, iterate over all.
            primary = aspects[0]
            pred_aspect = primary.get("aspecto_oficial", "General")
            pred_sentiment = primary.get("sentimiento", "Neutral")

            try:
                verdict = _call_judge(client, text, pred_aspect, pred_sentiment)
            except Exception as exc:
                logger.error("Judge API error for %s: %s", cid, exc)
                verdict = {
                    "relevancia_aspecto": 0,
                    "aspecto_correcto": False,
                    "sentimiento_correcto": False,
                    "sentimiento_real": "Error",
                    "explicacion": f"API error: {exc}",
                }

            # FIX #6 — include both predicted and real string labels
            judged = {
                "comment_id": cid,
                "model": model_key,
                "aspecto_predicho": pred_aspect,
                "sentimiento_predicho": pred_sentiment,
                "relevancia_aspecto": verdict.get("relevancia_aspecto", 0),
                "aspecto_correcto": verdict.get("aspecto_correcto", False),
                "sentimiento_correcto": verdict.get("sentimiento_correcto", False),
                "sentimiento_real": verdict.get("sentimiento_real", "Neutral"),
                "explicacion": verdict.get("explicacion", ""),
            }

            fh.write(json.dumps(judged, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(judged)
            time.sleep(DELAY_BETWEEN_CALLS)

    logger.info(
        "✓ Judge evaluation complete for %s: %d records.", model_key, len(results)
    )
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Phase C — LLM-as-a-Judge (GPT-4o) evaluator.",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=MODEL_KEYS,
        help="Model key whose outputs to judge.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Judge ALL model outputs sequentially.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set. Required for GPT-4o judge.")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    models_to_judge: List[str] = []
    if args.all:
        models_to_judge = MODEL_KEYS
    elif args.model:
        models_to_judge = [args.model]
    else:
        logger.error("Specify --model or --all.")
        return

    for model_key in models_to_judge:
        logger.info("=" * 60)
        logger.info("Judging model: %s (judge: %s)", model_key, JUDGE_MODEL)
        logger.info("=" * 60)
        evaluate_model(model_key, client)


if __name__ == "__main__":
    main()
