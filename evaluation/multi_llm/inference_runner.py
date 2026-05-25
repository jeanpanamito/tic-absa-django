#!/usr/bin/env python3
"""
Phase B — Unified multi-LLM inference runner.

Processes the same 700-comment sample through any supported model using
identical ABSA prompts.  Supports both OpenAI (GPT-4o-mini, GPT-4o) and
Google Gemini (2.0 Flash, 1.5 Pro, 2.5 Pro) providers.

Features:
  - Pre-computed embeddings (no per-model re-computation).
  - Incremental JSONL persistence (resume on failure).
  - tenacity retry with exponential backoff.
  - 0.5 s delay between API calls.

Usage:
    python -m evaluation.multi_llm.inference_runner --model gpt-4o-mini
    python -m evaluation.multi_llm.inference_runner --model gemini-2.0-flash
    python -m evaluation.multi_llm.inference_runner --all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
)
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("inference_runner")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_700_labeled.csv"
EMBEDDINGS_NPZ = PROJECT_ROOT / "data" / "sample_700_embeddings.npz"
ASPECT_VECTORS_JSON = PROJECT_ROOT / "data" / "aspect_vectors.json"
ONTOLOGY_JSON = PROJECT_ROOT / "data" / "exports" / "ontology_aspects.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

# ---------------------------------------------------------------------------
# Prompt import — single source of truth
# ---------------------------------------------------------------------------
from evaluation.prompts import ABSA_SYSTEM_PROMPT, build_absa_user_prompt

# ---------------------------------------------------------------------------
# Model registry — FIX #4: verified names, including version suffix
# ---------------------------------------------------------------------------

MODELS: Dict[str, Dict[str, str]] = {
    "gpt-4o-mini":      {"provider": "openai",  "model": "gpt-4o-mini"},
    "gpt-4o":           {"provider": "openai",  "model": "gpt-4o"},
    "gemini-2.0-flash": {"provider": "google",  "model": "gemini-2.0-flash"},
    "gemini-2.5-flash": {"provider": "google",  "model": "gemini-2.5-flash"},
    "gemini-2.5-pro":   {"provider": "google",  "model": "gemini-2.5-pro"},
}

# Inference constants
TEMPERATURE = 0.0
MAX_COMPLETION_TOKENS = 1_000
DELAY_BETWEEN_CALLS = 0.5


def validate_model_names() -> None:
    """Log exact model names — critical for paper reproducibility."""
    for key, cfg in MODELS.items():
        logger.info("Model key '%s' → API name: '%s' (provider: %s)",
                     key, cfg["model"], cfg["provider"])


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def _normalize(v: np.ndarray) -> np.ndarray:
    """L2-normalize a vector."""
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-12 else v


def compute_similarities(
    comment_emb: np.ndarray,
    aspect_vectors: Dict[str, List[float]],
) -> Dict[str, float]:
    """Compute cosine similarity between a comment and each aspect vector."""
    sims: Dict[str, float] = {}
    c_norm = _normalize(comment_emb)
    for name, vec in aspect_vectors.items():
        a_norm = _normalize(np.asarray(vec, dtype=np.float32))
        sims[name] = float(np.clip(np.dot(c_norm, a_norm), -1.0, 1.0))
    return sims


# ---------------------------------------------------------------------------
# Provider-specific inference
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_openai(
    client: Any,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """Call an OpenAI model with JSON mode."""
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        response_format={"type": "json_object"},
    )
    latency = time.perf_counter() - t0

    return {
        "content": response.choices[0].message.content,
        "prompt_tokens": int(response.usage.prompt_tokens) if response.usage else 0,
        "completion_tokens": int(response.usage.completion_tokens) if response.usage else 0,
        "latency_s": latency,
    }

def _is_quota_error(exc: BaseException) -> bool:
    """Return True if this is a 429 / ResourceExhausted quota error."""
    name = type(exc).__name__
    msg = str(exc)
    return "ResourceExhausted" in name or "429" in msg or "quota" in msg.lower()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_gemini(
    model_obj: Any,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """Call a Google Gemini model with JSON mode."""
    import google.generativeai as genai

    # Gemini uses system_instruction at model creation, which we already set.
    # The user prompt is passed as content.
    t0 = time.perf_counter()
    response = model_obj.generate_content(
        user_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=TEMPERATURE,
            max_output_tokens=MAX_COMPLETION_TOKENS,
        ),
    )
    latency = time.perf_counter() - t0

    content = response.text if response.text else ""
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

    return {
        "content": content,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "latency_s": latency,
    }


# ---------------------------------------------------------------------------
# Main inference loop
# ---------------------------------------------------------------------------


def run_inference(
    model_key: str,
    df: pd.DataFrame,
    embeddings: np.ndarray,
    emb_ids: List[str],
    aspect_vectors: Dict[str, List[float]],
    ontologia: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run ABSA inference on the 700-comment sample for a given model.

    Args:
        model_key: Key from ``MODELS`` dict (e.g. ``"gpt-4o-mini"``).
        df: Sample DataFrame.
        embeddings: Pre-computed comment embeddings.
        emb_ids: Comment IDs aligned to ``embeddings``.
        aspect_vectors: Pre-computed aspect reference vectors.
        ontologia: SKOS aspect ontology dict.

    Returns:
        List of per-comment inference result dicts.
    """
    cfg = MODELS[model_key]
    provider = cfg["provider"]
    model_name = cfg["model"]

    load_dotenv(PROJECT_ROOT / ".env")

    # --- Initialize client ---
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        gemini_model = None
    elif provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        gemini_model = genai.GenerativeModel(
            model_name,
            system_instruction=ABSA_SYSTEM_PROMPT,
        )
        client = None
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # --- Resume support ---
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = RESULTS_DIR / f"{model_key}.jsonl"
    processed_ids: set[str] = set()
    results: List[Dict[str, Any]] = []

    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    processed_ids.add(rec["comment_id"])
                    results.append(rec)
        logger.info("Resumed %d records from %s", len(processed_ids), jsonl_path)

    # --- Build ID→embedding lookup ---
    id_to_idx: Dict[str, int] = {cid: i for i, cid in enumerate(emb_ids)}

    # --- Deduplicate comments ---
    unique_comments = (
        df[["comment_id", "comment_text"]]
        .drop_duplicates(subset=["comment_id"])
        .reset_index(drop=True)
    )
    pending = unique_comments[
        ~unique_comments["comment_id"].isin(processed_ids)
    ]
    logger.info(
        "Model=%s | Total unique=%d | Already done=%d | Pending=%d",
        model_key, len(unique_comments), len(processed_ids), len(pending),
    )

    with open(jsonl_path, "a", encoding="utf-8") as fh:
        for _, row in tqdm(
            pending.iterrows(),
            total=len(pending),
            desc=f"Inference [{model_key}]",
        ):
            cid = str(row["comment_id"])
            text = str(row["comment_text"])

            # Compute similarities using pre-computed embedding
            idx = id_to_idx.get(cid)
            if idx is not None:
                sims = compute_similarities(embeddings[idx], aspect_vectors)
            else:
                sims = {name: 0.0 for name in aspect_vectors}

            user_prompt = build_absa_user_prompt(text, ontologia, sims)

            json_parse_error = False
            predicted_aspects: List[Dict[str, Any]] = []
            raw = ""
            prompt_tokens = 0
            completion_tokens = 0
            latency = 0.0

            try:
                if provider == "openai":
                    resp = _call_openai(
                        client, model_name, ABSA_SYSTEM_PROMPT, user_prompt
                    )
                else:
                    resp = _call_gemini(gemini_model, ABSA_SYSTEM_PROMPT, user_prompt)

                raw = resp["content"]
                prompt_tokens = resp["prompt_tokens"]
                completion_tokens = resp["completion_tokens"]
                latency = resp["latency_s"]

                try:
                    parsed = json.loads(raw)
                    predicted_aspects = parsed.get("aspectos", [])
                except json.JSONDecodeError:
                    json_parse_error = True
                    logger.warning("JSON parse error for comment %s", cid)

            except Exception as exc:
                if _is_quota_error(exc):
                    logger.critical(
                        "QUOTA EXHAUSTED for model %s — stopping inference. "
                        "Reset is typically daily. Error: %s",
                        model_key, exc,
                    )
                    raise SystemExit(
                        f"\n[FATAL] Gemini quota exhausted for '{model_key}'.\n"
                        f"The free-tier daily limit has been reached.\n"
                        f"Wait until tomorrow or enable billing at https://console.cloud.google.com/billing\n"
                        f"Then re-run: python -m evaluation.run_all_experiments --skip-export --skip-baselines --models {model_key}\n"
                    ) from exc
                logger.error("API error for %s on model %s: %s", cid, model_key, exc)

            record = {
                "comment_id": cid,
                "comment_text": text,
                "model": model_key,
                "predicted_aspects": predicted_aspects,
                "raw_response": raw[:2000] if json_parse_error else raw,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_s": round(latency, 4),
                "json_parse_error": json_parse_error,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(record)
            time.sleep(DELAY_BETWEEN_CALLS)

    logger.info("✓ Inference complete for %s: %d records.", model_key, len(results))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Phase B — Multi-LLM ABSA inference runner.",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=list(MODELS.keys()),
        help="Model key to run (e.g. gpt-4o-mini).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run inference for ALL registered models sequentially.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(SAMPLE_CSV),
        help="Path to the 700-comment sample CSV.",
    )
    return parser.parse_args()


def _load_prerequisites(
    csv_path: Path,
) -> Tuple[pd.DataFrame, np.ndarray, List[str], Dict[str, List[float]], Dict[str, Any]]:
    """Load all shared data files."""
    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    emb_data = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    embeddings = emb_data["embeddings"]
    emb_ids = list(emb_data["ids"])

    with open(ASPECT_VECTORS_JSON, "r", encoding="utf-8") as fh:
        aspect_vectors = json.load(fh)

    with open(ONTOLOGY_JSON, "r", encoding="utf-8") as fh:
        ontology_data = json.load(fh)
    ontologia = ontology_data["ontologia_aspectos"]

    return df, embeddings, emb_ids, aspect_vectors, ontologia


def main() -> None:
    """Entry point."""
    args = parse_args()
    validate_model_names()

    csv_path = Path(args.input)
    for required in [csv_path, EMBEDDINGS_NPZ, ASPECT_VECTORS_JSON, ONTOLOGY_JSON]:
        if not required.exists():
            logger.error("Required file missing: %s", required)
            logger.error("Run export_neo4j_sample.py first.")
            return

    df, embeddings, emb_ids, aspect_vectors, ontologia = _load_prerequisites(csv_path)

    models_to_run: List[str] = []
    if args.all:
        models_to_run = list(MODELS.keys())
    elif args.model:
        models_to_run = [args.model]
    else:
        logger.error("Specify --model or --all.")
        return

    for model_key in models_to_run:
        logger.info("=" * 60)
        logger.info("Starting inference: %s", model_key)
        logger.info("=" * 60)
        run_inference(
            model_key, df, embeddings, emb_ids, aspect_vectors, ontologia
        )


if __name__ == "__main__":
    main()
