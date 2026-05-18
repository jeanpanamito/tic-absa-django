#!/usr/bin/env python3
"""
Pipeline ABSA con embeddings reales (OpenAI) + Node2Vec.

Fase siguiente del proyecto que integra:
  * Ontología exportada por `skos_builder`
  * Comentarios reales de cursos extraídos (HG / EVOLFUND)
  * Embeddings de texto (OpenAI)
  * Embeddings de grafo (Node2Vec sobre la ontología)
  * Llamada a GPT para etiquetado ABSA asistido

Uso:
  python -m src.absa.semantic_pipeline --limit 20 --base-course EVOLFUND
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
    import networkx as nx  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - depende de instalación local
    raise ImportError(
        "networkx es requerido para ejecutar el pipeline ABSA. "
        "Instala con 'pip install networkx'."
    ) from exc

import numpy as np
import pandas as pd

try:
    from node2vec import Node2Vec  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - depende de instalación local
    raise ImportError(
        "node2vec es requerido para ejecutar el pipeline ABSA. "
        "Instala con 'pip install node2vec'."
    ) from exc

try:
    from openai import OpenAI  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - depende de instalación local
    raise ImportError(
        "openai (>=1.0) es requerido para ejecutar el pipeline ABSA. "
        "Instala con 'pip install openai'."
    ) from exc

from src.graph_construction.skos_builder import (
    CURSOS_DIR,
    EXPORT_DIR,
    INPUT_EVOLFUND_JSON,
    INPUT_HG_JSON,
    _read_records_from_json,
    load_ontology_from_json,
)

# Intentar cargar desde config
try:
    from config import OPENAI_API_KEY as CONFIG_OPENAI_KEY
except ImportError:
    CONFIG_OPENAI_KEY = None

# --- CONFIGURACIÓN OPENAI -------------------------------------------------

DEFAULT_GPT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_COMPLETION_TOKENS = 1_000

PRECIO_EMBEDDING_POR_1M_TOKENS = 0.02
PRECIO_GPT_INPUT_POR_1M_TOKENS = 0.15
PRECIO_GPT_OUTPUT_POR_1M_TOKENS = 0.60


# --- CONFIGURACIÓN NODE2VEC -----------------------------------------------

NODE2VEC_DIMENSIONS = 128
NODE2VEC_WALK_LENGTH = 30
NODE2VEC_NUM_WALKS = 200
NODE2VEC_WORKERS = 4


# --- ESTRUCTURAS DE DATOS -------------------------------------------------

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


# --- UTILIDADES -----------------------------------------------------------


def _ensure_openai_client(api_key: Optional[str]) -> Tuple[OpenAI, str]:
    key = api_key or os.environ.get("OPENAI_API_KEY") or CONFIG_OPENAI_KEY
    if not key:
        raise ValueError(
            "No se encontró una API Key para OpenAI. "
            "Configura la variable de entorno OPENAI_API_KEY o usa --api-key."
        )
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
    """Imprime texto de forma segura manejando caracteres Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Si hay error de codificación, reemplazar caracteres problemáticos
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text)


# --- FASE D: EMBEDDINGS TEXTUALES -----------------------------------------


def generar_embedding_openai(
    client: OpenAI,
    texto: str,
    embedding_model: str,
) -> Tuple[Optional[np.ndarray], int]:
    """
    Genera embeddings textuales usando la API de OpenAI.
    Devuelve el embedding (np.ndarray) y el total de tokens consumidos.
    """
    if not texto.strip():
        return None, 0

    try:
        response = client.embeddings.create(model=embedding_model, input=texto)
        embedding = _safe_numpy_array(response.data[0].embedding)
        tokens_usados = int(response.usage.total_tokens) if response.usage else 0
        return embedding, tokens_usados
    except Exception as exc:  # pragma: no cover - ruta dependiente de red
        print(f"   [ERROR] Error en API de OpenAI Embeddings: {exc}")
        return None, 0


def precomputar_embeddings_aspectos(
    ontologia: Dict[str, Dict[str, Optional[str]]],
    client: OpenAI,
    embedding_model: str,
) -> Tuple[Dict[str, np.ndarray], int]:
    """
    Genera embeddings de OpenAI para cada aspecto de la ontología,
    basándose en su nombre y descripción.
    """
    print("\n   -> Generando embeddings de referencia para la ontología (OpenAI)...")
    embeddings_aspectos = {}
    total_tokens = 0

    for aspecto, info in ontologia.items():
        descripcion = info.get("descripcion", "")
        # Construimos un texto representativo del aspecto
        texto_aspecto = f"Aspecto: {aspecto}. Descripción: {descripcion}"
        
        emb, tokens = generar_embedding_openai(client, texto_aspecto, embedding_model)
        if emb is not None:
            embeddings_aspectos[aspecto] = emb
            total_tokens += tokens
            
    print(f"   -> Embeddings generados para {len(embeddings_aspectos)} aspectos.")
    return embeddings_aspectos, total_tokens


# --- FASE E: GRAFO Y NODE2VEC ---------------------------------------------


def construir_grafo_conocimiento(
    ontologia: Dict[str, Dict[str, Optional[str]]],
    relaciones: Iterable[Tuple[str, str, str]],
) -> nx.DiGraph:
    grafo = nx.DiGraph()
    for aspecto, info in ontologia.items():
        grafo.add_node(aspecto, descripcion=info.get("descripcion"))

    for aspecto, info in ontologia.items():
        padre = info.get("padre")
        if padre:
            grafo.add_edge(padre, aspecto, tipo="jerarquia")

    for sujeto, predicado, objeto in relaciones:
        if grafo.has_node(sujeto) and grafo.has_node(objeto):
            grafo.add_edge(sujeto, objeto, tipo=predicado)

    return grafo


def entrenar_node2vec(
    grafo: nx.Graph,
    dimensions: int = NODE2VEC_DIMENSIONS,
    walk_length: int = NODE2VEC_WALK_LENGTH,
    num_walks: int = NODE2VEC_NUM_WALKS,
) -> Node2Vec:
    print("\n   -> Inicializando Node2Vec...")
    node2vec = Node2Vec(
        grafo,
        dimensions=dimensions,
        walk_length=walk_length,
        num_walks=num_walks,
        workers=NODE2VEC_WORKERS,
        p=1,
        q=1,
        seed=42,
    )
    print("   -> Entrenando modelo Node2Vec (esto puede tomar un momento)...")
    return node2vec.fit(window=10, min_count=1, batch_words=4)


def obtener_embedding_grafo(
    aspecto: str,
    modelo_node2vec,
) -> Optional[np.ndarray]:
    try:
        return _safe_numpy_array(modelo_node2vec.wv[aspecto])
    except KeyError:
        print(f"   [WARNING] Aspecto '{aspecto}' no encontrado en el modelo Node2Vec")
        return None


# --- FASE F: FUSIÓN MULTIMODAL --------------------------------------------


def fusionar_embeddings(
    embedding_texto: np.ndarray,
    embedding_grafo: np.ndarray,
    peso_texto: float = 0.6,
) -> np.ndarray:
    emb_texto_norm = _normalize_vector(embedding_texto)
    emb_grafo_norm = _normalize_vector(embedding_grafo)

    if emb_texto_norm.shape == emb_grafo_norm.shape:
        peso_grafo = 1.0 - peso_texto
        emb_fusionado = (peso_texto * emb_texto_norm) + (peso_grafo * emb_grafo_norm)
    else:
        emb_fusionado = np.concatenate(
            [emb_texto_norm * peso_texto, emb_grafo_norm * (1.0 - peso_texto)]
        )

    return _normalize_vector(emb_fusionado)


def calcular_similitud_coseno(vec1: np.ndarray, vec2: np.ndarray) -> float:
    v1 = _normalize_vector(vec1)
    v2 = _normalize_vector(vec2)
    if not v1.size or not v2.size:
        return 0.0
    return float(np.clip(np.dot(v1, v2), -1.0, 1.0))


# --- FASE G: GPT PARA ABSA ------------------------------------------------


def llamar_gpt_absa(
    client: OpenAI,
    comentario_texto: str,
    ontologia: Dict[str, Dict[str, Optional[str]]],
    similitudes_embedding: Optional[Dict[str, float]],
    gpt_model: str,
    temperature: float,
    max_completion_tokens: int,
) -> Tuple[Dict, int, int]:
    aspectos_jerarquicos: List[str] = []

    for aspecto, info in ontologia.items():
        aspecto_str = f"   - {aspecto}"
        if info.get("padre"):
            aspecto_str += f" (subcategoría de {info['padre']})"
        descripcion = info.get("descripcion")
        if descripcion:
            aspecto_str += f": {descripcion}"
        if similitudes_embedding and aspecto in similitudes_embedding:
            sim = similitudes_embedding[aspecto]
            # Resaltar aspectos con alta similitud para guiar al modelo
            if sim > 0.4:  # Umbral ajustado para embeddings OpenAI
                aspecto_str = f"*** {aspecto_str} [ALTA RELEVANCIA: {sim:.2f}] ***"
            elif sim > 0.25:
                aspecto_str += f" [Relevancia: {sim:.2f}]"
        aspectos_jerarquicos.append(aspecto_str)

    system_prompt = """Eres un asistente experto en análisis de sentimientos basado en aspectos (ABSA) para comentarios de foros educativos.

Tu tarea es:
1. Identificar todos los aspectos educativos mencionados en el comentario
2. Usar ÚNICAMENTE los aspectos de la ontología proporcionada
3. Determinar el sentimiento (Positivo, Negativo o Neutral) para cada aspecto
4. Extraer la frase exacta que justifica tu análisis

IMPORTANTE:
- Mapea términos informales a conceptos formales (ej: "test", "examen" -> "Evaluacion")
- Considera las relevancia semántica indicadas en los aspectos
- Un comentario puede tener múltiples aspectos con diferentes sentimientos
- Responde SOLO con JSON válido sin texto adicional"""

    user_prompt = f"""**ONTOLOGÍA DE ASPECTOS:**
{os.linesep.join(aspectos_jerarquicos)}

**COMENTARIO:**
"{comentario_texto}"

**FORMATO JSON (SOLO ESTE FORMATO):**
{{
  "aspectos": [
    {{
      "aspecto_oficial": "<nombre exacto del aspecto>",
      "sentimiento": "<Positivo|Negativo|Neutral>",
      "mencion_original": "<frase del texto>",
      "justificacion": "<explicación breve>",
      "confianza": <0.0-1.0>
    }}
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model=gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            response_format={"type": "json_object"},
        )

        contenido = response.choices[0].message.content
        resultado = json.loads(contenido)

        prompt_tokens = (
            int(response.usage.prompt_tokens) if response.usage else 0
        )
        completion_tokens = (
            int(response.usage.completion_tokens) if response.usage else 0
        )

        return resultado, prompt_tokens, completion_tokens

    except json.JSONDecodeError as exc:
        print(f"   [ERROR] Error al parsear JSON: {exc}")
        if "contenido" in locals():
            print(f"   Contenido recibido: {contenido[:200]}...")
        return {"aspectos": []}, 0, 0
    except Exception as exc:  # pragma: no cover - dependiente de red
        print(f"   [ERROR] Error en API de OpenAI: {exc}")
        return {"aspectos": []}, 0, 0


# --- CARGA DE DATOS -------------------------------------------------------


def cargar_comentarios(
    limit: int,
    base_course: Optional[str] = None,
    min_characters: int = 20,
) -> List[Comentario]:
    fuentes = [INPUT_HG_JSON, INPUT_EVOLFUND_JSON]
    dfs = []
    for src in fuentes:
        if os.path.exists(src):
            dfs.append(_read_records_from_json(src))

    if not dfs:
        raise FileNotFoundError(
            f"No se encontraron archivos de comentarios en {CURSOS_DIR}"
        )

    df = pd.concat(dfs, ignore_index=True, sort=False)

    if base_course:
        df = df[df["base_course"].astype(str).str.lower() == base_course.lower()]

    df = df.dropna(subset=["comment_id", "text"]).copy()
    df["comment_id"] = df["comment_id"].astype(str)
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() >= min_characters]
    df = df.drop_duplicates(subset=["comment_id"])

    if df.empty:
        raise ValueError("No hay comentarios que cumplan los filtros seleccionados.")

    if limit and len(df) > limit:
        df = df.head(limit)

    comentarios = [
        Comentario(
            comment_id=row.comment_id,
            text=row.text,
            course_id=getattr(row, "course_id", None),
            base_course=getattr(row, "base_course", None),
            thread_id=getattr(row, "thread_id", None),
        )
        for row in df.itertuples(index=False)
    ]

    return comentarios


def cargar_ontologia(json_path: Optional[str]) -> Tuple[Dict, List[Tuple[str, str, str]]]:
    ontology_raw = load_ontology_from_json(json_path)
    return ontology_raw["ontologia_aspectos"], ontology_raw["relaciones_aspectos"]


# --- CHECKPOINT Y RECUPERACIÓN --------------------------------------------


# --- RESULTADOS Y CHECKPOINT ----------------------------------------------


def guardar_chunk(
    resultados: List[ResultadoABSA],
    output_dir: Path,
    chunk_index: int,
) -> None:
    """Guarda un chunk de resultados en un archivo separado."""
    if not resultados:
        return
        
    filename = f"resultados_absa_part_{chunk_index:04d}.json"
    output_path = output_dir / filename
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    resultados_dict = [
        {
            "id_comentario": r.id_comentario,
            "aspecto": r.aspecto,
            "sentimiento": r.sentimiento,
            "mencion": r.mencion,
            "justificacion": r.justificacion,
            "confianza": r.confianza,
            "similitud_embedding": r.similitud_embedding,
            "embedding_dimension": r.embedding_dimension,
            "course_id": r.course_id,
            "base_course": r.base_course,
            "thread_id": r.thread_id,
            "vector_fusionado": r.vector_fusionado,
            "vector_texto": r.vector_texto,
            "vector_grafo": r.vector_grafo,
        }
        for r in resultados
    ]
    
    with output_path.open("w", encoding="utf-8") as fo:
        json.dump(resultados_dict, fo, ensure_ascii=False, indent=2)
    
    print(f"   [Sistema] Chunk {chunk_index} guardado en {filename} ({len(resultados)} registros)")


def guardar_checkpoint(
    comentarios_procesados: set[str],
    total_embedding_tokens: int,
    total_prompt_tokens: int,
    total_completion_tokens: int,
    checkpoint_path: Path,
) -> None:
    """Guarda el estado actual del procesamiento (SOLO IDs Y TOKENS)."""
    checkpoint_data = {
        "comentarios_procesados": list(comentarios_procesados),
        "total_embedding_tokens": total_embedding_tokens,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        # YA NO GUARDAMOS 'resultados' AQUÍ PARA EVITAR ARCHIVOS GIGANTES
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("w", encoding="utf-8") as f:
        json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)


def cargar_checkpoint(checkpoint_path: Path) -> Tuple[set[str], int, int, int]:
    """Carga el estado guardado de un checkpoint (SIN RESULTADOS)."""
    if not checkpoint_path.exists():
        return set(), 0, 0, 0
    
    with checkpoint_path.open("r", encoding="utf-8") as f:
        checkpoint_data = json.load(f)
    
    comentarios_procesados = set(checkpoint_data.get("comentarios_procesados", []))
    
    # Checkpoint antiguo podría traer resultados, los ignoramos porque ya deberían estar en chunks si se migró,
    # o si es fresh start no habrá. Si es resume de old run, se perderían resultados no guardados en chunks.
    # ASUMIMOS MIGRACIÓN O NUEVA EJECUCIÓN (CHUNK-BASED).
    
    total_embedding_tokens = checkpoint_data.get("total_embedding_tokens", 0)
    total_prompt_tokens = checkpoint_data.get("total_prompt_tokens", 0)
    total_completion_tokens = checkpoint_data.get("total_completion_tokens", 0)
    
    return comentarios_procesados, total_embedding_tokens, total_prompt_tokens, total_completion_tokens


# --- COSTOS ---------------------------------------------------------------


def calcular_costos(
    tokens_embeddings: int,
    tokens_prompt: int,
    tokens_completion: int,
) -> Dict[str, float]:
    costo_embeddings = (tokens_embeddings / 1_000_000) * PRECIO_EMBEDDING_POR_1M_TOKENS
    costo_prompt = (tokens_prompt / 1_000_000) * PRECIO_GPT_INPUT_POR_1M_TOKENS
    costo_completion = (tokens_completion / 1_000_000) * PRECIO_GPT_OUTPUT_POR_1M_TOKENS
    costo_total = costo_embeddings + costo_prompt + costo_completion
    return {
        "embeddings": costo_embeddings,
        "prompt": costo_prompt,
        "completion": costo_completion,
        "total": costo_total,
    }


# --- PIPELINE -------------------------------------------------------------


def ejecutar_pipeline(
    comentarios: List[Comentario],
    ontologia: Dict,
    relaciones: List[Tuple[str, str, str]],
    client: OpenAI,
    gpt_model: str,
    embedding_model: str,
    temperature: float,
    max_completion_tokens: int,
    output_dir: Path, # Changed from output_path to output_dir
    api_key_present: bool,
    checkpoint_path: Optional[Path] = None,
    resume: bool = False,
    checkpoint_interval: int = 10,
    chunk_size: int = 500,
) -> None:
    print("=" * 80)
    print(f"PIPELINE COMPLETO: OpenAI Embeddings + Node2Vec + {gpt_model}")
    print("=" * 80)
    print(f"\n[OK] API Key configurada: {api_key_present}")
    print(f"[OK] Modelo LLM: {gpt_model}")
    print(f"[OK] Modelo Embeddings: {embedding_model}")
    print(f"[OK] Chunk Size: {chunk_size}")

    print(f"\n{'=' * 80}")
    print("[FASE E] Construyendo grafo de conocimiento y entrenando Node2Vec")
    print(f"{'=' * 80}")

    grafo = construir_grafo_conocimiento(ontologia, relaciones)
    # ... (Node2Vec training code omitted for brevity as it is identical)
    # Actually, I need to include it or reference it properly if I am replacing the whole function block.
    # Since I'm using replace_file_content on a range, I must be careful.
    
    # Let's keep the existing structure and just replace the function implementations
    # and the logic inside ejecutar_pipeline.
    # The tool use above replaces from line 447 to 600 approx.
    # I should include the actual Node2Vec execution if I'm replacing the start of ejecutar_pipeline
    
    # RE-INSERTING NODE2VEC LOGIC WHICH WAS CUT OFF IN PREVIOUS THOUGHT
    
    print(f"\n[OK] Grafo construido:")
    print(f"   - Nodos (aspectos): {grafo.number_of_nodes()}")
    print(f"   - Aristas (relaciones): {grafo.number_of_edges()}")

    modelo_node2vec = entrenar_node2vec(grafo)

    print(f"\n[OK] Node2Vec entrenado:")
    print(f"   - Dimensiones: {NODE2VEC_DIMENSIONS}")
    print(f"   - Vocabulario: {len(modelo_node2vec.wv)}")

    print("\n   Generando embeddings de grafo (Node2Vec)...")
    embeddings_grafo_node2vec: Dict[str, np.ndarray] = {}
    for aspecto in ontologia.keys():
        emb = obtener_embedding_grafo(aspecto, modelo_node2vec)
        if emb is not None:
            embeddings_grafo_node2vec[aspecto] = emb
            # print(f"     [OK] {aspecto}: {len(emb)}D") # Verbose off

    print(f"\n[FASE D-PRE] Precomputando embeddings semánticos de aspectos (OpenAI)...")
    embeddings_aspectos_openai, tokens_init = precomputar_embeddings_aspectos(
        ontologia, client, embedding_model
    )
    # Sumar estos tokens al total (se hará en el loop o variable global, 
    # aquí lo retornamos para sumarlo después)
    total_embedding_tokens_init = tokens_init

    # Cargar checkpoint si se solicita continuar
    comentarios_procesados: set[str] = set()
    buffer_resultados: List[ResultadoABSA] = []
    chunk_index = 1
    total_embedding_tokens = total_embedding_tokens_init
    total_prompt_tokens = 0
    total_completion_tokens = 0
    
    if resume and checkpoint_path and checkpoint_path.exists():
        print(f"\n[OK] Cargando checkpoint desde: {checkpoint_path.as_posix()}")
        comentarios_procesados, total_embedding_tokens, total_prompt_tokens, total_completion_tokens = cargar_checkpoint(checkpoint_path)
        print(f"[OK] Checkpoint cargado: {len(comentarios_procesados)} comentarios ya procesados")
        
        # Determinar el siguiente chunk index
        if output_dir.exists():
            existing_chunks = list(output_dir.glob("resultados_absa_part_*.json"))
            if existing_chunks:
                last_chunk = sorted(existing_chunks)[-1]
                try:
                    last_num = int(last_chunk.stem.split('_')[-1])
                    chunk_index = last_num + 1
                except ValueError:
                    pass
        print(f"[OK] Continuando desde chunk {chunk_index}")
        print(f"[OK] Continuando desde el comentario {len(comentarios_procesados) + 1}...")
    
    # Filtrar comentarios ya procesados
    comentarios_pendientes = [c for c in comentarios if c.comment_id not in comentarios_procesados]
    total_comentarios = len(comentarios)
    comentarios_ya_procesados = len(comentarios_procesados)
    
    print(f"\n[OK] Total comentarios: {total_comentarios}")
    print(f"[OK] Ya procesados: {comentarios_ya_procesados}")
    print(f"[OK] Pendientes: {len(comentarios_pendientes)}")

    try:
        for idx, comentario in enumerate(comentarios_pendientes, start=comentarios_ya_procesados + 1):
            print(f"\n{'=' * 80}")
            print(f"COMENTARIO {idx}/{total_comentarios}: {comentario.comment_id}")
            print(f"{'=' * 80}")
            _safe_print(f"Texto: {comentario.text}")

            try:
                print("\n[FASE D] Generando embedding textual (OpenAI)...")
                embedding_texto, emb_tokens = generar_embedding_openai(
                    client, comentario.text, embedding_model
                )
                total_embedding_tokens += emb_tokens

                if embedding_texto is None:
                    print("   [WARNING] Error al generar embedding, saltando comentario")
                    comentarios_procesados.add(comentario.comment_id)
                    continue

                print(f"   [OK] Embedding generado: {len(embedding_texto)}D ({emb_tokens} tokens)")

                print("\n[FASE F] Calculando similitudes semánticas (OpenAI vs OpenAI)...")
                similitudes: Dict[str, float] = {}
                for aspecto, emb_aspecto_openai in embeddings_aspectos_openai.items():
                    similitudes[aspecto] = calcular_similitud_coseno(embedding_texto, emb_aspecto_openai)

                top_aspectos = sorted(similitudes.items(), key=lambda x: x[1], reverse=True)[:3]
                print("   Top 3 aspectos por similitud:")
                for aspecto, sim in top_aspectos:
                    print(f"     - {aspecto}: {sim:.3f}")

                print("\n[FASE G] Analizando con LLM...")
                respuesta_llm, p_tokens, c_tokens = llamar_gpt_absa(
                    client=client,
                    comentario_texto=comentario.text,
                    ontologia=ontologia,
                    similitudes_embedding=similitudes,
                    gpt_model=gpt_model,
                    temperature=temperature,
                    max_completion_tokens=max_completion_tokens,
                )

                total_prompt_tokens += p_tokens
                total_completion_tokens += c_tokens
                print(f"   [OK] Respuesta recibida (Prompt: {p_tokens} tokens, Output: {c_tokens} tokens)")

                aspectos_respuesta = respuesta_llm.get("aspectos") or []
                if not aspectos_respuesta:
                    print("   [WARNING] No se detectaron aspectos")
                    comentarios_procesados.add(comentario.comment_id)
                    continue

                print(f"   [OK] Detectados {len(aspectos_respuesta)} aspectos")

                print("\n[FASE H] Generando tripletas SPO y Fusión para registro...")
                for aspecto_data in aspectos_respuesta:
                    aspecto_nombre = aspecto_data.get("aspecto_oficial", "General")
                    emb_grafo = embeddings_grafo_node2vec.get(aspecto_nombre)
                    
                    emb_texto_para_fusion = embedding_texto
                    if emb_grafo is not None:
                        dim_grafo = len(emb_grafo)
                        if len(embedding_texto) > dim_grafo:
                             emb_texto_para_fusion = embedding_texto[:dim_grafo]
                        emb_fusionado = fusionar_embeddings(emb_texto_para_fusion, emb_grafo)
                    else:
                        emb_fusionado = _normalize_vector(embedding_texto)

                    tripleta = ResultadoABSA(
                        id_comentario=comentario.comment_id,
                        aspecto=aspecto_nombre,
                        sentimiento=aspecto_data.get("sentimiento", "Neutral"),
                        mencion=aspecto_data.get("mencion_original", ""),
                        justificacion=aspecto_data.get("justificacion", ""),
                        confianza=float(aspecto_data.get("confianza", 0.0)),
                        similitud_embedding=float(similitudes.get(aspecto_nombre, 0.0)),
                        embedding_dimension=int(len(emb_fusionado)),
                        course_id=comentario.course_id,
                        base_course=comentario.base_course,
                        thread_id=comentario.thread_id,
                        vector_fusionado=emb_fusionado.tolist(),
                        vector_texto=embedding_texto.tolist(),
                        vector_grafo=emb_grafo.tolist() if emb_grafo is not None else None,
                    )

                    print(f"\n   {tripleta.aspecto} -> {tripleta.sentimiento}")
                    print(f"     Confianza: {tripleta.confianza:.2f}")
                    print(f"     Similitud: {tripleta.similitud_embedding:.3f}")
                    
                    buffer_resultados.append(tripleta)
                
                comentarios_procesados.add(comentario.comment_id)
                
                if len(buffer_resultados) >= chunk_size:
                    guardar_chunk(buffer_resultados, output_dir, chunk_index)
                    buffer_resultados = []
                    chunk_index += 1
                
                if checkpoint_path and (idx % checkpoint_interval == 0):
                    guardar_checkpoint(
                        comentarios_procesados,
                        total_embedding_tokens,
                        total_prompt_tokens,
                        total_completion_tokens,
                        checkpoint_path,
                    )
                    print(f"\n[OK] Checkpoint guardado (comentario {idx}/{total_comentarios})")

            except Exception as exc:
                print(f"\n[ERROR] Error procesando comentario {comentario.comment_id}: {exc}")
                print(f"[WARNING] Continuando con el siguiente comentario...")
                continue

    except KeyboardInterrupt:
        print("\n\n[WARNING] Proceso interrumpido por el usuario")
    
    finally:
        if buffer_resultados:
            print("\n[FINAL] Guardando resultados restantes en buffer...")
            guardar_chunk(buffer_resultados, output_dir, chunk_index)
            
        if checkpoint_path:
             guardar_checkpoint(
                comentarios_procesados,
                total_embedding_tokens,
                total_prompt_tokens,
                total_completion_tokens,
                checkpoint_path,
            )
             print("\n[OK] Checkpoint final guardado")

    print(f"\n{'=' * 80}")
    print("RESUMEN FINAL")
    print(f"{'=' * 80}")
    print(f"\n[OK] Comentarios procesados: {len(comentarios_procesados)}/{total_comentarios}")
    
    costos = calcular_costos(total_embedding_tokens, total_prompt_tokens, total_completion_tokens)
    print(f"\n   COSTO TOTAL ESTIMADO: ${costos['total']:.6f} USD")
    print(f"{'=' * 80}\n")
    
    # Ya no retornamos 'resultados_finales' porque con chunking no los tenemos todos en memoria
    # Pero si el script espera devolver algo, devolvemos None o lista vacía
    return []


# --- CLI ------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline ABSA con embeddings reales.")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Número máximo de comentarios a procesar.",
    )
    parser.add_argument(
        "--base-course",
        type=str,
        default=None,
        help="Filtrar por base_course (por ejemplo: EVOLFUND).",
    )
    parser.add_argument(
        "--min-characters",
        type=int,
        default=30,
        help="Longitud mínima del comentario para ser considerado.",
    )
    parser.add_argument(
        "--ontology-json",
        type=str,
        default=str(Path(EXPORT_DIR) / "ontology_aspects.json"),
        help="Ruta al JSON de ontología exportado por skos_builder.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(EXPORT_DIR) / "resultados_absa_completo.json"),
        help="Ruta de salida para los resultados ABSA.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API Key de OpenAI (alternativa a la variable de entorno OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--gpt-model",
        type=str,
        default=DEFAULT_GPT_MODEL,
        help="Modelo GPT para análisis ABSA.",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help="Modelo de embeddings de texto.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Temperatura para la generación de texto.",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=DEFAULT_MAX_COMPLETION_TOKENS,
        help="Tokens máximos para la respuesta del modelo GPT.",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Ruta al archivo de checkpoint para guardar/continuar progreso.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continuar desde el último checkpoint guardado.",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Intervalo de comentarios para guardar checkpoint (default: 10).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Cantidad de comentarios por archivo chunk (default: 1000).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    comentarios = cargar_comentarios(
        limit=args.limit,
        base_course=args.base_course,
        min_characters=args.min_characters,
    )
    ontologia, relaciones = cargar_ontologia(args.ontology_json)
    client, resolved_key = _ensure_openai_client(args.api_key)
    output_path = Path(args.output)
    
    # OUTPUT PATH ahora se trata como un directorio si se usa chunking, 
    # pero el usuario pasa un archivo usualmente.
    output_dir = output_path.parent
    
    # Configurar checkpoint
    checkpoint_path = None
    if args.checkpoint:
        checkpoint_path = Path(args.checkpoint)
    elif args.resume:
        checkpoint_path = output_dir / "checkpoint.json"
    
    ejecutar_pipeline(
        comentarios=comentarios,
        ontologia=ontologia,
        relaciones=relaciones,
        client=client,
        gpt_model=args.gpt_model,
        embedding_model=args.embedding_model,
        temperature=args.temperature,
        max_completion_tokens=args.max_completion_tokens,
        output_dir=output_dir,
        api_key_present=bool(resolved_key),
        checkpoint_path=checkpoint_path,
        resume=args.resume,
        checkpoint_interval=args.checkpoint_interval,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()


