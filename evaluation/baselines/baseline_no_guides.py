#!/usr/bin/env python3
"""
Baseline A3 — GPT-4o-mini WITHOUT vector candidate guides (ablation).

Runs the full ABSA prompt through GPT-4o-mini but with
``similitudes=None``, so no ``*** ALTA RELEVANCIA ***`` markers are
injected into the aspect list.  This isolates the contribution of the
cosine-similarity candidate injection mechanism.

Usage:
    python -m evaluation.baselines.baseline_no_guides
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
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
logger = logging.getLogger("baseline_no_guides")

# ---------------------------------------------------------------------------
# Paths & Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
ONTOLOGY_JSON = PROJECT_ROOT / "data" / "exports" / "ontology_aspects.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
MAX_COMPLETION_TOKENS = 1_000
DELAY_BETWEEN_CALLS = 0.5


# ---------------------------------------------------------------------------
# Prompt import — single source of truth
# ---------------------------------------------------------------------------
from evaluation.prompts import (
    ABSA_SYSTEM_PROMPT,
    build_absa_user_prompt_no_guides,
)


# ---------------------------------------------------------------------------
# OpenAI call with retry
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_openai(
    client: Any,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """Call GPT-4o-mini with JSON mode and exponential backoff.

    Returns:
        Dict with keys: ``response``, ``prompt_tokens``, ``completion_tokens``.
    """
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        response_format={"type": "json_object"},
    )
    latency = time.perf_counter() - t0

    content = response.choices[0].message.content
    prompt_tokens = int(response.usage.prompt_tokens) if response.usage else 0
    completion_tokens = int(response.usage.completion_tokens) if response.usage else 0

    return {
        "content": content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_s": latency,
    }


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def run_no_guides_baseline(
    df: pd.DataFrame,
    ontologia: Dict[str, Any],
    output_path: Path,
) -> List[Dict[str, Any]]:
    """Run GPT-4o-mini ABSA without candidate guides.

    Saves incrementally to JSONL for resilience.

    Args:
        df: 700-triple sample.
        ontologia: Aspect ontology dict.
        output_path: Path to write results JSON.

    Returns:
        List of result dicts.
    """
    from openai import OpenAI

    load_dotenv(PROJECT_ROOT / ".env")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Load existing results for resume
    processed_ids: set[str] = set()
    results: List[Dict[str, Any]] = []
    jsonl_path = output_path.with_suffix(".jsonl")

    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                processed_ids.add(rec["comment_id"])
                results.append(rec)
        logger.info("Resumed: %d comments already processed.", len(processed_ids))

    # De-duplicate: process unique comments only
    unique_comments = (
        df[["comment_id", "comment_text"]]
        .drop_duplicates(subset=["comment_id"])
        .reset_index(drop=True)
    )

    pending = unique_comments[
        ~unique_comments["comment_id"].isin(processed_ids)
    ]
    logger.info("Pending: %d unique comments to process.", len(pending))

    with open(jsonl_path, "a", encoding="utf-8") as fh:
        for _, row in tqdm(
            pending.iterrows(), total=len(pending), desc="No-guides baseline"
        ):
            cid = str(row["comment_id"])
            text = str(row["comment_text"])

            user_prompt = build_absa_user_prompt_no_guides(text, ontologia)

            json_parse_error = False
            predicted_aspects: List[Dict[str, Any]] = []

            try:
                resp = _call_openai(client, ABSA_SYSTEM_PROMPT, user_prompt)
                raw = resp["content"]

                try:
                    parsed = json.loads(raw)
                    predicted_aspects = parsed.get("aspectos", [])
                except json.JSONDecodeError:
                    json_parse_error = True
                    logger.warning("JSON parse error for %s", cid)

            except Exception as exc:
                logger.error("API error for %s: %s", cid, exc)
                raw = ""
                resp = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "latency_s": 0.0,
                }

            record = {
                "comment_id": cid,
                "comment_text": text,
                "model": "no_guides_ablation",
                "predicted_aspects": predicted_aspects,
                "raw_response": raw if not json_parse_error else raw[:500],
                "prompt_tokens": resp["prompt_tokens"],
                "completion_tokens": resp["completion_tokens"],
                "latency_s": round(resp["latency_s"], 4),
                "json_parse_error": json_parse_error,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(record)
            time.sleep(DELAY_BETWEEN_CALLS)

    # Also write full JSON
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Baseline A3 — GPT-4o-mini without candidate guides.",
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
        logger.error("Sample CSV not found: %s", csv_path)
        return

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    # Load ontology
    if not ONTOLOGY_JSON.exists():
        logger.error("Ontology not found: %s", ONTOLOGY_JSON)
        return

    with open(ONTOLOGY_JSON, "r", encoding="utf-8") as fh:
        ontology_data = json.load(fh)
    ontologia = ontology_data["ontologia_aspectos"]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline_no_guides.json"

    results = run_no_guides_baseline(df, ontologia, out_path)
    logger.info("✓ No-guides baseline → %s (%d rows)", out_path, len(results))


if __name__ == "__main__":
    main()
