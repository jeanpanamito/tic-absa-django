#!/usr/bin/env python3
"""
Pipeline ABSA específico para el curso SRM.
Adaptado de semantic_pipeline.py para procesar contenido_curso_srm.json.

Uso:
  python -m src.absa.semantic_pipeline_srm --limit 500
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import networkx as nx
except ImportError as exc:
    raise ImportError("networkx es requerido. Instala con 'pip install networkx'.") from exc

import numpy as np
import pandas as pd

try:
    from node2vec import Node2Vec
except ImportError as exc:
    raise ImportError("node2vec es requerido. Instala con 'pip install node2vec'.") from exc

try:
    from openai import OpenAI
except ImportError as exc:
    raise ImportError("openai (>=1.0) es requerido. Instala con 'pip install openai'.") from exc

# Reutilizamos funciones de skos_builder si es necesario, o cargamos directo
from src.graph_construction.skos_builder import (
    load_ontology_from_json,
    EXPORT_DIR
)

# Intentar cargar desde config
try:
    from config import OPENAI_API_KEY as CONFIG_OPENAI_KEY
except ImportError:
    CONFIG_OPENAI_KEY = None

# --- CONFIGURACIÓN ESTÁTICA ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
INPUT_SRM_JSON = os.path.join(PROJECT_ROOT, 'contenido_curso_srm.json')
OUTPUT_DIR_SRM = os.path.join(PROJECT_ROOT, 'data', 'exports', 'resultados_srm')

DEFAULT_GPT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_COMPLETION_TOKENS = 1_000

# Node2Vec Config
NODE2VEC_DIMENSIONS = 128
NODE2VEC_WALK_LENGTH = 30
NODE2VEC_NUM_WALKS = 200
NODE2VEC_WORKERS = 4

# --- ESTRUCTURAS DE DATOS ---

@dataclass
class Comentario:
    comment_id: str
    text: str
    course_id: Optional[str] = None
    base_course: Optional[str] = None
    thread_id: Optional[str] = None

@dataclass
class ResultadoABSA:
    id_comentario: str
    aspecto: str
    sentimiento: str
    mencion: str
    justificacion: str
    confianza: float
    similitud_embedding: float
    embedding_dimension: int
    course_id: Optional[str] = None
    base_course: Optional[str] = None
    thread_id: Optional[str] = None
    vector_fusionado: Optional[List[float]] = None
    vector_texto: Optional[List[float]] = None
    vector_grafo: Optional[List[float]] = None

# --- UTILIDADES ---

def _ensure_openai_client(api_key: Optional[str]) -> Tuple[OpenAI, str]:
    key = api_key or os.environ.get("OPENAI_API_KEY") or CONFIG_OPENAI_KEY
    if not key:
        raise ValueError("No API Key found. Set OPENAI_API_KEY env var.")
    return OpenAI(api_key=key), key

def _safe_numpy_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.ndim != 1:
        arr = arr.flatten()
    return arr

def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    epsilon = 1e-12
    norm = np.linalg.norm(vector)
    if norm < epsilon:
        return vector
    return vector / norm

def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text)

# --- FASE D: EMBEDDINGS TEXTUALES ---

def generar_embedding_openai(client: OpenAI, texto: str, model: str) -> Tuple[Optional[np.ndarray], int]:
    if not texto.strip():
        return None, 0
    try:
        response = client.embeddings.create(model=model, input=texto)
        embedding = _safe_numpy_array(response.data[0].embedding)
        tokens = int(response.usage.total_tokens) if response.usage else 0
        return embedding, tokens
    except Exception as exc:
        print(f"   [ERROR] OpenAI Embeddings: {exc}")
        return None, 0

def precomputar_embeddings_aspectos(ontologia: Dict, client: OpenAI, model: str) -> Dict[str, np.ndarray]:
    print("\n   -> Generando embeddings de referencia para la ontología (OpenAI)...")
    embeddings = {}
    for aspecto, info in ontologia.items():
        desc = info.get("descripcion", "")
        texto = f"Aspecto: {aspecto}. Descripción: {desc}"
        emb, _ = generar_embedding_openai(client, texto, model)
        if emb is not None:
            embeddings[aspecto] = emb
    return embeddings

# --- FASE E: GRAFO Y NODE2VEC ---

def construir_grafo_conocimiento(ontologia: Dict, relaciones: Iterable[Tuple[str, str, str]]) -> nx.DiGraph:
    grafo = nx.DiGraph()
    for aspecto, info in ontologia.items():
        grafo.add_node(aspecto, descripcion=info.get("descripcion"))
    for aspecto, info in ontologia.items():
        padre = info.get("padre")
        if padre:
            grafo.add_edge(padre, aspecto, tipo="jerarquia")
    for s, p, o in relaciones:
        if grafo.has_node(s) and grafo.has_node(o):
            grafo.add_edge(s, o, tipo=p)
    return grafo

def entrenar_node2vec(grafo: nx.Graph) -> Node2Vec:
    print("\n   -> Entrenando Node2Vec...")
    node2vec = Node2Vec(grafo, dimensions=NODE2VEC_DIMENSIONS, walk_length=NODE2VEC_WALK_LENGTH, num_walks=NODE2VEC_NUM_WALKS, workers=NODE2VEC_WORKERS, p=1, q=1, seed=42)
    return node2vec.fit(window=10, min_count=1, batch_words=4)

def obtener_embedding_grafo(aspecto: str, model) -> Optional[np.ndarray]:
    try:
        return _safe_numpy_array(model.wv[aspecto])
    except KeyError:
        return None

# --- FASE F: FUSIÓN ---

def fusionar_embeddings(txt_emb: np.ndarray, graph_emb: np.ndarray, peso_txt: float = 0.6) -> np.ndarray:
    txt_norm = _normalize_vector(txt_emb)
    graph_norm = _normalize_vector(graph_emb)
    if txt_norm.shape == graph_norm.shape:
        fused = (peso_txt * txt_norm) + ((1 - peso_txt) * graph_norm)
    else:
        # Concatenación simple si dimensiones difieren y no hacemos proyección
        fused = np.concatenate([txt_norm * peso_txt, graph_norm * (1 - peso_txt)])
    return _normalize_vector(fused)

def calcular_similitud_coseno(vec1: np.ndarray, vec2: np.ndarray) -> float:
    v1 = _normalize_vector(vec1)
    v2 = _normalize_vector(vec2)
    if not v1.size or not v2.size: return 0.0
    return float(np.clip(np.dot(v1, v2), -1.0, 1.0))

# --- FASE G: GPT ABSA ---

def llamar_gpt_absa(client: OpenAI, texto: str, ontologia: Dict, similitudes: Dict, model: str) -> Tuple[Dict, int, int]:
    aspectos_str_list = []
    for aspecto, info in ontologia.items():
        line = f"- {aspecto}"
        if info.get("padre"): line += f" (sub de {info['padre']})"
        if info.get("descripcion"): line += f": {info['descripcion']}"
        sim = similitudes.get(aspecto, 0.0)
        if sim > 0.35: line = f"*** {line} [RELEVANTE: {sim:.2f}] ***"
        aspectos_str_list.append(line)

    system_prompt = """Eres un experto en ABSA educativo.
Tarea:
1. Identificar aspectos del texto usando SOLO la ontología dada.
2. Determinar sentimiento (Positivo/Negativo/Neutral).
3. Extraer justificación textual exacta.
Responde SOLO JSON válido."""

    user_prompt = f"""**ONTOLOGÍA:**
{os.linesep.join(aspectos_str_list)}

**TEXTO:**
"{texto}"

**JSON:**
{{
  "aspectos": [
    {{
      "aspecto_oficial": "Nombre",
      "sentimiento": "Positivo/Negativo/Neutral",
      "mencion_original": "frase",
      "justificacion": "explicacion",
      "confianza": 0.9
    }}
  ]
}}"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=DEFAULT_TEMPERATURE,
            max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        return json.loads(content), int(resp.usage.prompt_tokens), int(resp.usage.completion_tokens)
    except Exception as e:
        print(f"   [ERROR] GPT: {e}")
        return {"aspectos": []}, 0, 0

# --- CARGA DE DATOS SRM ---

def cargar_comentarios_srm(limit: int = 0, min_chars: int = 20) -> List[Comentario]:
    if not os.path.exists(INPUT_SRM_JSON):
        raise FileNotFoundError(f"No se encontró {INPUT_SRM_JSON}")
    
    with open(INPUT_SRM_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # La estructura es { "curso": "SRM", "comentarios": [ ... ] }
    raw_comments = data.get("comentarios", [])
    
    comentarios = []
    for rc in raw_comments:
        txt = str(rc.get("text", "")).strip()
        if len(txt) < min_chars:
            continue
            
        c = Comentario(
            comment_id=str(rc.get("id")),
            text=txt,
            course_id=str(rc.get("course_id", "")),
            base_course="SRM",
            thread_id=str(rc.get("thread_id", ""))
        )
        comentarios.append(c)
        
    print(f"Cargados {len(comentarios)} comentarios brutos de SRM.")
    
    if limit > 0 and len(comentarios) > limit:
        comentarios = comentarios[:limit]
        
    return comentarios

# --- PRINCIPAL ---

def guardar_chunk(resultados: List[ResultadoABSA], output_dir: Path, index: int):
    if not resultados: return
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"resultados_absa_part_{index:04d}.json"
    data = [
        {
            "id_comentario": r.id_comentario,
            "mencion_original": r.mencion,
            "aspecto": r.aspecto,
            "sentimiento": r.sentimiento,
            "justificacion": r.justificacion,
            "confianza": r.confianza,
            "base_course": r.base_course,
            "vector_texto": r.vector_texto,
            "vector_grafo": r.vector_grafo,
            "vector_fusionado": r.vector_fusionado
        }
        for r in resultados
    ]
    with (output_dir / filename).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   [Sistema] Guardado chunk {index} en {filename}")

def main():
    parser = argparse.ArgumentParser(description="Pipeline ABSA para SRM")
    parser.add_argument("--limit", type=int, default=0, help="Límite de comentarios")
    parser.add_argument("--api-key", type=str, help="OpenAI API Key")
    args = parser.parse_args()

    client, _ = _ensure_openai_client(args.api_key)
    
    # Cargar Ontología
    ontology_raw = load_ontology_from_json() # Usa path por defecto en data/exports
    ontologia = ontology_raw["ontologia_aspectos"]
    relaciones = ontology_raw["relaciones_aspectos"]

    # Cargar Comentarios SRM
    comentarios = cargar_comentarios_srm(limit=args.limit)
    print(f"Procesando {len(comentarios)} comentarios finales.")

    # Grafo + Node2Vec
    grafo = construir_grafo_conocimiento(ontologia, relaciones)
    n2v_model = entrenar_node2vec(grafo)
    
    # Loop
    buffer = []
    chunk_idx = 1
    out_path = Path(OUTPUT_DIR_SRM)
    
    # Precomputar embeddings aspectos (simplificado para no repetir en loop si no cambia)
    emb_aspectos = precomputar_embeddings_aspectos(ontologia, client, DEFAULT_EMBEDDING_MODEL)

    # Precomputar embeddings grafo (Node2Vec) para acceso rápido
    print("\n   Generando embeddings de grafo (Node2Vec)...")
    embeddings_grafo_node2vec = {}
    for aspecto in ontologia.keys():
        emb = obtener_embedding_grafo(aspecto, n2v_model)
        if emb is not None:
            embeddings_grafo_node2vec[aspecto] = emb

    for i, com in enumerate(comentarios):
        print(f"\n--- Comentario {i+1}/{len(comentarios)}: {com.comment_id} ---")
        _safe_print(com.text[:100] + "...")
        
        # 1. Embedding Texto
        emb_txt, _ = generar_embedding_openai(client, com.text, DEFAULT_EMBEDDING_MODEL)
        if emb_txt is None: continue

        # 2. Similitud
        sims = {asp: calcular_similitud_coseno(emb_txt, emb_asp) for asp, emb_asp in emb_aspectos.items()}
        
        # 3. LLM
        res_llm, _, _ = llamar_gpt_absa(client, com.text, ontologia, sims, DEFAULT_GPT_MODEL)
        
        found = False
        for item in res_llm.get("aspectos", []):
            found = True
            aspecto_nom = item.get("aspecto_oficial", "General")
            
            # Fusión de Embeddings
            emb_grafo = embeddings_grafo_node2vec.get(aspecto_nom)
            if emb_grafo is not None:
                # Truncar texto si es mayor (auqnue txt es 1536 y grafo 128, fusionar_embeddings maneja tamaños distintos con concat o weighted avg si iguales)
                # La función definida 'fusionar_embeddings' maneja dimensionalidad distinta concatenando.
                emb_fusionado = fusionar_embeddings(emb_txt, emb_grafo)
            else:
                 # Si no hay grafo, usamos el de texto normalizado
                emb_fusionado = _normalize_vector(emb_txt)
            
            r = ResultadoABSA(
                id_comentario=com.comment_id,
                aspecto=aspecto_nom,
                sentimiento=item.get("sentimiento", "Neutral"),
                mencion=item.get("mencion_original", ""),
                justificacion=item.get("justificacion", ""),
                confianza=float(item.get("confianza", 0.0)),
                similitud_embedding=sims.get(aspecto_nom, 0.0),
                embedding_dimension=int(len(emb_fusionado)),
                base_course="SRM",
                vector_fusionado=emb_fusionado.tolist(),
                vector_texto=emb_txt.tolist(),
                vector_grafo=emb_grafo.tolist() if emb_grafo is not None else None
            )
            buffer.append(r)
            print(f"   -> {r.aspecto}: {r.sentimiento}")

        if not found:
            print("   (Sin aspectos detectados)")

        if len(buffer) >= 50:
            guardar_chunk(buffer, out_path, chunk_idx)
            buffer = []
            chunk_idx += 1

    if buffer:
        guardar_chunk(buffer, out_path, chunk_idx)

if __name__ == "__main__":
    main()
