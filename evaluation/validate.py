#!/usr/bin/env python3
"""
Validation Module for ABSA Pipeline (LLM-as-a-Judge).
"""

import argparse
import json
import os
import random
from typing import Dict, List, Any
import pandas as pd
from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("openai module required. pip install openai")

# Intentar cargar desde config
try:
    from config import OPENAI_API_KEY as CONFIG_OPENAI_KEY
except ImportError:
    CONFIG_OPENAI_KEY = None

# --- CONFIG ---
DEFAULT_MODEL = "gpt-4o-mini" # User mentioned gpt-4o, using mini for cost efficiency unless specified, or change to gpt-4o
# Actually user specifically asked for "GPT-4o". I will default to gpt-4o but allow override.
JUDGE_MODEL = "gpt-4o" 

def load_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def evaluate_comment(client: OpenAI, item: Dict, ontology_keys: set) -> Dict:
    """
    Evaluates a single ABSA result item using LLM-as-a-Judge.
    Input item usually has: text, aspecto, sentimiento, justificacion
    (Note: pipeline output has 'mencion' as justificacion snippet, or we need to look up original text if not present.
     The pipeline output `ResultadoABSA` doesn't strictly carry the FULL original text always, 
     but `semantic_pipeline_srm.py` saves basic info. 
     WAIT: The output JSON from pipeline has: id_comentario, aspecto, sentimiento, justificacion...
     It does NOT have the full text. We might need to look it up or pass it if available.
     
     The prompt requirements say: "Evaluates if the extracted aspect is relevant to the text". 
     We need the TEXT.
     
     Solution: We will load the original SRM json to create a lookup map {id -> text}.
    """
    
    # 1. Ontological Compliance
    aspect = item.get("aspecto", "")
    is_compliant = aspect in ontology_keys
    
    # Return early or continue? We can evaluate alignment even if not in ontology, but usually it's better to proceed.
    
    return {
        "ontological_compliance": is_compliant,
        # Placeholders for LLM metrics
        "alignment_score": 0,
        "sentiment_consistent": False,
        "reasoning": "Skipped LLM"
    }

def llm_judge(client: OpenAI, text: str, aspect: str, sentiment: str, justification: str) -> Dict:
    system_prompt = """You are an impartial judge evaluating an Aspect-Based Sentiment Analysis (ABSA) system.
    
    You will receive:
    1. Original User Comment
    2. Extracted Aspect
    3. Extracted Sentiment
    4. Extracted Justification (Snippet)
    
    Your task is to evaluate:
    1. Aspect Alignment Score (1-5): Is the aspect relevant to the text?
       1: Hallucination/Irrelevant
       5: Perfect/Explicit
    2. Sentiment Consistency (Boolean): Does the assigned sentiment logicall match the text/justification?
    
    Return JSON."""
    
    user_prompt = f"""
    COMMENT: "{text}"
    
    SYSTEM OUTPUT:
    - Aspect: {aspect}
    - Sentiment: {sentiment}
    - Justification: "{justification}"
    
    Respond in JSON:
    {{
        "alignment_score": <int 1-5>,
        "sentiment_consistent": <bool>,
        "reasoning": "<short explanation>"
    }}
    """
    
    try:
        resp = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {"alignment_score": 1, "sentiment_consistent": False, "reasoning": f"Error: {e}"}

def main():
    parser = argparse.ArgumentParser(description="ABSA Validator (LLM-as-a-Judge)")
    parser.add_argument("--input-file", required=True, help="Path to ABSA results JSON (or chunk)")
    parser.add_argument("--ontology-file", required=True, help="Path to Ontology JSON")
    parser.add_argument("--original-file", required=True, help="Path to original comments JSON (SRM) for text lookup")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of items to evaluate (to save costs)")
    parser.add_argument("--api-key", help="OpenAI API Key")
    parser.add_argument("--output-dir", default="data/exports/validation", help="Dir for reports")
    
    args = parser.parse_args()
    
    # Setup OpenAI
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") or CONFIG_OPENAI_KEY
    if not api_key:
        print("Warning: No API Key provided. LLM evaluation will fail.")
        # We might want to raise error or allow running only struct checks?
        # User specified "Desarrollador Senior... generar un script ROBUSTO". 
        # raising error is better.
        # raise ValueError("OpenAI API Key required.")
        # actually let's assume env var is there or passed
    
    client = OpenAI(api_key=api_key) if api_key else None

    # Load Ontology
    print(f"Loading ontology from {args.ontology_file}...")
    ontology_data = load_json(args.ontology_file)
    # Support both raw dict or wrapped structure
    if "ontologia_aspectos" in ontology_data:
        ontology_keys = set(ontology_data["ontologia_aspectos"].keys())
    else:
        ontology_keys = set(ontology_data.keys())
        
    # Load Original Text Map
    print(f"Loading original texts from {args.original_file}...")
    orig_data = load_json(args.original_file)
    # SRM structure: {"comentarios": [{"id":..., "text":...}]}
    # Or generically check records
    if "comentarios" in orig_data:
        raw_list = orig_data["comentarios"]
    elif "records" in orig_data:
        raw_list = orig_data["records"]
    else:
        raw_list = [] # Fallback or error
        
    id_to_text = {str(item.get("id") or item.get("comment_id")): item.get("text", "") for item in raw_list}
    
    # Load Results
    print(f"Loading results from {args.input_file}...")
    results = load_json(args.input_file)
    # results is list of dicts
    
    # Sampling
    if len(results) > args.sample_size:
        print(f"Sampling {args.sample_size} random items from {len(results)} total.")
        sample = random.sample(results, args.sample_size)
    else:
        sample = results
        
    print(f"Starting evaluation of {len(sample)} items...")
    
    audit_log = []
    stats = {
        "ontological_compliance": 0,
        "aspect_alignment_total": 0,
        "sentiment_consistency_count": 0,
        "total_evaluated": 0
    }
    
    for item in tqdm(sample):
        cid = str(item.get("id_comentario"))
        text = id_to_text.get(cid, "")
        
        # 1. Compliance
        aspect = item.get("aspecto", "General")
        is_compliant = aspect in ontology_keys
        
        stats["total_evaluated"] += 1
        if is_compliant:
            stats["ontological_compliance"] += 1
            
        # 2. LLM Judge
        llm_res = {"alignment_score": 0, "sentiment_consistent": False, "reasoning": "No Text Found"}
        if client and text:
             llm_res = llm_judge(client, text, aspect, item.get("sentimiento", ""), item.get("justificacion", ""))
        
        stats["aspect_alignment_total"] += llm_res.get("alignment_score", 0)
        if llm_res.get("sentiment_consistent"):
            stats["sentiment_consistency_count"] += 1
            
        record = {
            "comment_id": cid,
            "text_snippet": text[:50],
            "aspect": aspect,
            "sentiment": item.get("sentimiento"),
            "ontological_compliance": is_compliant,
            "alignment_score": llm_res.get("alignment_score", 0),
            "sentiment_consistent": llm_res.get("sentiment_consistent", False),
            "reasoning": llm_res.get("reasoning", "")
        }
        audit_log.append(record)
        
    # Validating division by zero
    total = max(stats["total_evaluated"], 1)
    
    final_metrics = {
        "ontological_compliance_rate": round(stats["ontological_compliance"] / total * 100, 2),
        "vocab_alignment_avg": round(stats["aspect_alignment_total"] / total, 2), # Using prompt terms: Aspect Alignment Score
        "sentiment_consistency_rate": round(stats["sentiment_consistency_count"] / total * 100, 2)
    }
    
    # Outputs
    os.makedirs(args.output_dir, exist_ok=True)
    
    # JSON Detailed
    with open(os.path.join(args.output_dir, "validation_results_detailed.json"), 'w', encoding='utf-8') as f:
        json.dump(audit_log, f, ensure_ascii=False, indent=2)
        
    # Markdown Report
    md_lines = [
        "# Chapter 5: Validation Report",
        "",
        "## Summary Metrics",
        f"- **Sample Size**: {total}",
        f"- **Ontological Compliance**: {final_metrics['ontological_compliance_rate']}%",
        f"- **Aspect Alignment Score (Avg)**: {final_metrics['vocab_alignment_avg']} / 5.0",
        f"- **Sentiment Consistency**: {final_metrics['sentiment_consistency_rate']}%",
        "",
        "## Failed Examples (Score < 3 or Inconsistent)",
        "| ID | Aspect | Sentiment | Score | Consistent? | Reasoning |",
        "|---|---|---|---|---|---|"
    ]
    
    for r in audit_log:
        if r["alignment_score"] < 3 or not r["sentiment_consistent"]:
            row = f"| {r['comment_id']} | {r['aspect']} | {r['sentiment']} | {r['alignment_score']} | {r['sentiment_consistent']} | {r['reasoning']} |"
            md_lines.append(row)
            
    md_path = os.path.join(args.output_dir, "validation_report.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    print("\n" + "="*40)
    print("VALIDATION COMPLETE")
    print(f"Report: {md_path}")
    print("="*40)
    print(json.dumps(final_metrics, indent=2))

if __name__ == "__main__":
    main()
