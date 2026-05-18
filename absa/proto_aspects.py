#!/usr/bin/env python3
"""
Prototipo ABSA (simple) para detección de aspectos y polaridad.
- Entrada: data/processed/cleaned_comments.csv
- Salidas:
  * data/exports/aspect_spo.csv (subject=comment, predicate=hasAspect, object=aspect)
  * data/exports/aspect_polarity.csv (comment, aspect, polarity)
  * data/exports/aspect_sample.ttl (TTL mínimo)

Uso:
  python -m src.absa.proto_aspects --limit 20000
"""

import os
import re
import argparse
import pandas as pd
from urllib.parse import quote

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'data', 'exports')
INPUT_CLEAN = os.path.join(PROCESSED_DIR, 'cleaned_comments.csv')
BASE = 'http://example.org/tic-absa/'

ASPECT_LEXICON = {
    'contenido': [r'\bcontenido\b', r'\bmaterial(es)?\b', r'\btema(s)?\b', r'\blecci[oó]n(es)?\b'],
    'docente': [r'\bdocente\b', r'\bprofesor(a)?\b', r'\binstructor(a)?\b', r'\btutor(a)?\b'],
    'evaluacion': [r'\bevaluaci[oó]n(es)?\b', r'\bexamen(es)?\b', r'\bprueba(s)?\b', r'\bcalificaci[oó]n(es)?\b'],
    'plataforma': [r'\bplataforma\b', r'\bsistema\b', r'\binterfaz\b', r'\bnavegaci[oó]n\b'],
    'interaccion': [r'\bforo(s)?\b', r'\bdiscusi[oó]n(es)?\b', r'\bcomentario(s)?\b', r'\brespuesta(s)?\b']
}

POSITIVE = [r'\bexcelente\b', r'\bbueno(a)?\b', r'\bclaro(a)?\b', r'\butil\b', r'\bgenial\b']
NEGATIVE = [r'\bmalo(a)?\b', r'\bdif[ií]cil\b', r'\bconfuso(a)?\b', r'\bproblema(s)?\b', r'\berror(es)?\b']


def iri(path: str) -> str:
    return BASE + quote(path, safe='/:#')


def ensure_dirs():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def detect_aspects(text: str) -> list:
    if not isinstance(text, str):
        return []
    found = set()
    for aspect, patterns in ASPECT_LEXICON.items():
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                found.add(aspect)
                break
    return sorted(found)


def detect_polarity(text: str) -> str:
    if not isinstance(text, str):
        return 'neutral'
    pos = any(re.search(p, text, flags=re.IGNORECASE) for p in POSITIVE)
    neg = any(re.search(p, text, flags=re.IGNORECASE) for p in NEGATIVE)
    if pos and not neg:
        return 'positive'
    if neg and not pos:
        return 'negative'
    if pos and neg:
        return 'mixed'
    return 'neutral'


def run(limit: int = 20000) -> None:
    ensure_dirs()
    df = pd.read_csv(INPUT_CLEAN)
    if limit and len(df) > limit:
        df = df.head(limit)

    spo_rows = []
    pol_rows = []

    for _, r in df.iterrows():
        cid = str(r['id'])
        text = str(r.get('text', ''))
        aspects = detect_aspects(text)
        if not aspects:
            continue
        polarity = detect_polarity(text)
        for a in aspects:
            spo_rows.append({'subject': iri(f'comment/{cid}'), 'predicate': 'absa:hasAspect', 'object': iri(f'aspect/{a}')})
            pol_rows.append({'comment': iri(f'comment/{cid}'), 'aspect': a, 'polarity': polarity})

    pd.DataFrame(spo_rows).to_csv(os.path.join(EXPORT_DIR, 'aspect_spo.csv'), index=False)
    pd.DataFrame(pol_rows).to_csv(os.path.join(EXPORT_DIR, 'aspect_polarity.csv'), index=False)

    # TTL mínimo
    ttl = []
    ttl.append('@prefix skos: <http://www.w3.org/2004/02/skos/core#> .')
    ttl.append('@prefix absa: <http://example.org/absa#> .')
    ttl.append(f'@base <{BASE}> .\n')
    for row in spo_rows[:1000]:
        ttl.append(f'<{row["subject"]}> absa:hasAspect <{row["object"]}> .')
    with open(os.path.join(EXPORT_DIR, 'aspect_sample.ttl'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(ttl))

    print(f"ABSA proto:")
    print(f"- SPO: {len(spo_rows):,} → data/exports/aspect_spo.csv")
    print(f"- Polaridad: {len(pol_rows):,} → data/exports/aspect_polarity.csv")
    print(f"- TTL: data/exports/aspect_sample.ttl")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20000)
    args = parser.parse_args()
    run(limit=args.limit)


if __name__ == '__main__':
    main()
