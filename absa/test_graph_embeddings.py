#!/usr/bin/env python3
"""
Script de prueba para generar y visualizar embeddings del grafo con Node2Vec.

Este script permite:
- Generar embeddings del grafo con diferentes dimensionalidades (128, 200, 300)
- Visualizar la matriz de embeddings generada
- Crear gráficas de visualización usando PCA y t-SNE para reducir a 2D
- Analizar similitudes entre aspectos

Uso:
  python -m src.absa.test_graph_embeddings --dimensions 128 200 300
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import networkx as nx  # type: ignore[import]
except ImportError as exc:
    raise ImportError(
        "networkx es requerido. Instala con 'pip install networkx'."
    ) from exc

import numpy as np
import pandas as pd

try:
    from node2vec import Node2Vec  # type: ignore[import]
except ImportError as exc:
    raise ImportError(
        "node2vec es requerido. Instala con 'pip install node2vec'."
    ) from exc

try:
    import matplotlib.pyplot as plt  # type: ignore[import]
    import seaborn as sns  # type: ignore[import]
    from sklearn.decomposition import PCA  # type: ignore[import]
    from sklearn.manifold import TSNE  # type: ignore[import]
    from sklearn.preprocessing import StandardScaler  # type: ignore[import]
except ImportError as exc:
    raise ImportError(
        "matplotlib, seaborn y scikit-learn son requeridos. "
        "Instala con 'pip install matplotlib seaborn scikit-learn'."
    ) from exc

from src.graph_construction.skos_builder import (
    EXPORT_DIR,
    load_ontology_from_json,
)


# --- CONFIGURACIÓN NODE2VEC -----------------------------------------------

NODE2VEC_WALK_LENGTH = 30
NODE2VEC_NUM_WALKS = 200
NODE2VEC_WORKERS = 4


# --- UTILIDADES -----------------------------------------------------------


def _safe_numpy_array(values) -> np.ndarray:
    """Convierte valores a un array numpy seguro."""
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.ndim != 1:
        arr = arr.flatten()
    return arr


def construir_grafo_conocimiento(
    ontologia: Dict[str, Dict[str, str | None]],
    relaciones: List[Tuple[str, str, str]],
) -> nx.DiGraph:
    """Construye el grafo de conocimiento a partir de la ontología."""
    grafo = nx.DiGraph()
    
    # Agregar nodos (aspectos)
    for aspecto, info in ontologia.items():
        grafo.add_node(aspecto, descripcion=info.get("descripcion"))
    
    # Agregar aristas jerárquicas (padre-hijo)
    for aspecto, info in ontologia.items():
        padre = info.get("padre")
        if padre:
            grafo.add_edge(padre, aspecto, tipo="jerarquia")
    
    # Agregar aristas de relaciones semánticas
    for sujeto, predicado, objeto in relaciones:
        if grafo.has_node(sujeto) and grafo.has_node(objeto):
            grafo.add_edge(sujeto, objeto, tipo=predicado)
    
    return grafo


def entrenar_node2vec(
    grafo: nx.Graph,
    dimensions: int,
    walk_length: int = NODE2VEC_WALK_LENGTH,
    num_walks: int = NODE2VEC_NUM_WALKS,
) -> Node2Vec:
    """Entrena un modelo Node2Vec con las dimensiones especificadas."""
    print(f"\n   -> Inicializando Node2Vec con {dimensions} dimensiones...")
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
    print(f"   -> Entrenando modelo Node2Vec...")
    return node2vec.fit(window=10, min_count=1, batch_words=4)


def obtener_embeddings_completos(
    ontologia: Dict[str, Dict[str, str | None]],
    modelo_node2vec: Node2Vec,
) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
    """
    Obtiene todos los embeddings de aspectos y la matriz completa.
    
    Returns:
        - Dict con aspecto -> embedding
        - Matriz numpy de shape (num_aspectos, dimensions)
    """
    embeddings_dict: Dict[str, np.ndarray] = {}
    aspectos_ordenados = sorted(ontologia.keys())
    
    for aspecto in aspectos_ordenados:
        try:
            emb = _safe_numpy_array(modelo_node2vec.wv[aspecto])
            embeddings_dict[aspecto] = emb
        except KeyError:
            print(f"   [WARNING] Aspecto '{aspecto}' no encontrado en el modelo")
            # Crear embedding cero si no existe
            dim = modelo_node2vec.wv.vector_size
            embeddings_dict[aspecto] = np.zeros(dim, dtype=np.float32)
    
    # Construir matriz
    matriz = np.array([embeddings_dict[asp] for asp in aspectos_ordenados])
    
    return embeddings_dict, matriz


def calcular_similitud_coseno(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calcula la similitud coseno entre dos vectores."""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.clip(np.dot(vec1, vec2) / (norm1 * norm2), -1.0, 1.0))


def visualizar_matriz_embeddings(
    matriz: np.ndarray,
    aspectos: List[str],
    dimensions: int,
    output_dir: Path,
) -> None:
    """Visualiza la matriz de embeddings como un heatmap."""
    print(f"\n   -> Generando visualización de matriz de embeddings...")
    
    # Crear DataFrame para mejor visualización
    df_matriz = pd.DataFrame(
        matriz,
        index=aspectos,
        columns=[f"Dim_{i+1}" for i in range(matriz.shape[1])]
    )
    
    # Guardar matriz como CSV
    csv_path = output_dir / f"matriz_embeddings_{dimensions}d.csv"
    df_matriz.to_csv(csv_path, encoding="utf-8")
    print(f"   [OK] Matriz guardada: {csv_path}")
    
    # Visualizar heatmap (muestra solo las primeras 20 dimensiones para legibilidad)
    max_dims_plot = min(20, matriz.shape[1])
    plt.figure(figsize=(14, max(8, len(aspectos) * 0.5)))
    sns.heatmap(
        df_matriz.iloc[:, :max_dims_plot],
        annot=False,
        cmap="coolwarm",
        center=0,
        cbar_kws={"label": "Valor del embedding"},
        xticklabels=[f"D{i+1}" for i in range(max_dims_plot)],
    )
    plt.title(f"Matriz de Embeddings - {dimensions} Dimensiones\n(Primeras {max_dims_plot} dimensiones)", 
              fontsize=14, fontweight="bold")
    plt.xlabel("Dimensiones", fontsize=12)
    plt.ylabel("Aspectos", fontsize=12)
    plt.tight_layout()
    
    heatmap_path = output_dir / f"heatmap_embeddings_{dimensions}d.png"
    plt.savefig(heatmap_path, dpi=300, bbox_inches="tight")
    print(f"   [OK] Heatmap guardado: {heatmap_path}")
    plt.close()


def visualizar_similitudes(
    embeddings_dict: Dict[str, np.ndarray],
    dimensions: int,
    output_dir: Path,
) -> None:
    """Genera una matriz de similitudes coseno entre aspectos."""
    print(f"\n   -> Calculando matriz de similitudes...")
    
    aspectos = sorted(embeddings_dict.keys())
    n = len(aspectos)
    matriz_sim = np.zeros((n, n))
    
    for i, asp1 in enumerate(aspectos):
        for j, asp2 in enumerate(aspectos):
            sim = calcular_similitud_coseno(embeddings_dict[asp1], embeddings_dict[asp2])
            matriz_sim[i, j] = sim
    
    # Guardar como CSV
    df_sim = pd.DataFrame(matriz_sim, index=aspectos, columns=aspectos)
    csv_path = output_dir / f"matriz_similitudes_{dimensions}d.csv"
    df_sim.to_csv(csv_path, encoding="utf-8")
    print(f"   [OK] Matriz de similitudes guardada: {csv_path}")
    
    # Visualizar
    plt.figure(figsize=(12, 10))
    sns.heatmap(
        df_sim,
        annot=True,
        fmt=".3f",
        cmap="RdYlBu_r",
        center=0,
        square=True,
        cbar_kws={"label": "Similitud Coseno"},
        linewidths=0.5,
    )
    plt.title(f"Matriz de Similitudes Coseno - {dimensions} Dimensiones", 
              fontsize=14, fontweight="bold")
    plt.xlabel("Aspectos", fontsize=12)
    plt.ylabel("Aspectos", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    sim_path = output_dir / f"similitudes_{dimensions}d.png"
    plt.savefig(sim_path, dpi=300, bbox_inches="tight")
    print(f"   [OK] Matriz de similitudes guardada: {sim_path}")
    plt.close()


def visualizar_pca(
    matriz: np.ndarray,
    aspectos: List[str],
    dimensions: int,
    output_dir: Path,
) -> None:
    """Reduce las dimensiones usando PCA y visualiza en 2D."""
    print(f"\n   -> Aplicando PCA para reducción a 2D...")
    
    # Normalizar antes de PCA
    scaler = StandardScaler()
    matriz_norm = scaler.fit_transform(matriz)
    
    # Aplicar PCA
    pca = PCA(n_components=2, random_state=42)
    matriz_2d = pca.fit_transform(matriz_norm)
    
    # Crear DataFrame
    df_pca = pd.DataFrame(
        matriz_2d,
        columns=["PC1", "PC2"],
        index=aspectos
    )
    
    # Guardar coordenadas
    csv_path = output_dir / f"pca_coordenadas_{dimensions}d.csv"
    df_pca.to_csv(csv_path, encoding="utf-8")
    print(f"   [OK] Coordenadas PCA guardadas: {csv_path}")
    print(f"   [INFO] Varianza explicada: PC1={pca.explained_variance_ratio_[0]:.2%}, "
          f"PC2={pca.explained_variance_ratio_[1]:.2%}")
    
    # Visualizar
    plt.figure(figsize=(12, 10))
    scatter = plt.scatter(
        df_pca["PC1"],
        df_pca["PC2"],
        s=200,
        alpha=0.7,
        edgecolors="black",
        linewidths=1.5,
    )
    
    # Anotar cada punto con el nombre del aspecto
    for aspecto, row in df_pca.iterrows():
        plt.annotate(
            aspecto,
            (row["PC1"], row["PC2"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=10,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5),
        )
    
    plt.xlabel(f"Primer Componente Principal (PC1) - {pca.explained_variance_ratio_[0]:.2%} varianza", 
               fontsize=12)
    plt.ylabel(f"Segundo Componente Principal (PC2) - {pca.explained_variance_ratio_[1]:.2%} varianza", 
               fontsize=12)
    plt.title(f"Visualización PCA de Embeddings - {dimensions} Dimensiones", 
              fontsize=14, fontweight="bold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    pca_path = output_dir / f"pca_visualizacion_{dimensions}d.png"
    plt.savefig(pca_path, dpi=300, bbox_inches="tight")
    print(f"   [OK] Visualización PCA guardada: {pca_path}")
    plt.close()


def visualizar_tsne(
    matriz: np.ndarray,
    aspectos: List[str],
    dimensions: int,
    output_dir: Path,
    perplexity: float = None,
) -> None:
    """Reduce las dimensiones usando t-SNE y visualiza en 2D."""
    print(f"\n   -> Aplicando t-SNE para reducción a 2D...")
    
    # Calcular perplexity automáticamente si no se proporciona
    if perplexity is None:
        perplexity = min(30, max(5, len(aspectos) - 1))
    
    # Normalizar antes de t-SNE
    scaler = StandardScaler()
    matriz_norm = scaler.fit_transform(matriz)
    
    # Aplicar t-SNE
    tsne = TSNE(n_components=2, random_state=42, perplexity=perplexity, max_iter=1000)
    matriz_2d = tsne.fit_transform(matriz_norm)
    
    # Crear DataFrame
    df_tsne = pd.DataFrame(
        matriz_2d,
        columns=["t-SNE 1", "t-SNE 2"],
        index=aspectos
    )
    
    # Guardar coordenadas
    csv_path = output_dir / f"tsne_coordenadas_{dimensions}d.csv"
    df_tsne.to_csv(csv_path, encoding="utf-8")
    print(f"   [OK] Coordenadas t-SNE guardadas: {csv_path}")
    
    # Visualizar
    plt.figure(figsize=(12, 10))
    scatter = plt.scatter(
        df_tsne["t-SNE 1"],
        df_tsne["t-SNE 2"],
        s=200,
        alpha=0.7,
        edgecolors="black",
        linewidths=1.5,
    )
    
    # Anotar cada punto con el nombre del aspecto
    for aspecto, row in df_tsne.iterrows():
        plt.annotate(
            aspecto,
            (row["t-SNE 1"], row["t-SNE 2"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=10,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5),
        )
    
    plt.xlabel("Primera Dimensión t-SNE", fontsize=12)
    plt.ylabel("Segunda Dimensión t-SNE", fontsize=12)
    plt.title(f"Visualización t-SNE de Embeddings - {dimensions} Dimensiones\n"
              f"(perplexity={perplexity})", 
              fontsize=14, fontweight="bold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    tsne_path = output_dir / f"tsne_visualizacion_{dimensions}d.png"
    plt.savefig(tsne_path, dpi=300, bbox_inches="tight")
    print(f"   [OK] Visualización t-SNE guardada: {tsne_path}")
    plt.close()


def generar_estadisticas_embeddings(
    embeddings_dict: Dict[str, np.ndarray],
    matriz: np.ndarray,
    dimensions: int,
    output_dir: Path,
) -> None:
    """Genera estadísticas descriptivas de los embeddings."""
    print(f"\n   -> Generando estadísticas descriptivas...")
    
    stats = {
        "dimensiones": dimensions,
        "num_aspectos": len(embeddings_dict),
        "estadisticas_por_aspecto": {},
        "estadisticas_globales": {
            "media": float(np.mean(matriz)),
            "std": float(np.std(matriz)),
            "min": float(np.min(matriz)),
            "max": float(np.max(matriz)),
            "mediana": float(np.median(matriz)),
        }
    }
    
    for aspecto, emb in embeddings_dict.items():
        stats["estadisticas_por_aspecto"][aspecto] = {
            "media": float(np.mean(emb)),
            "std": float(np.std(emb)),
            "min": float(np.min(emb)),
            "max": float(np.max(emb)),
            "norma_l2": float(np.linalg.norm(emb)),
        }
    
    # Guardar estadísticas
    stats_path = output_dir / f"estadisticas_embeddings_{dimensions}d.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"   [OK] Estadísticas guardadas: {stats_path}")
    
    # Crear tabla resumen
    df_stats = pd.DataFrame(stats["estadisticas_por_aspecto"]).T
    csv_path = output_dir / f"estadisticas_resumen_{dimensions}d.csv"
    df_stats.to_csv(csv_path, encoding="utf-8")
    print(f"   [OK] Tabla de estadísticas guardada: {csv_path}")


def procesar_dimension(
    dimensions: int,
    grafo: nx.DiGraph,
    ontologia: Dict[str, Dict[str, str | None]],
    output_dir: Path,
    generar_pca: bool = True,
    generar_tsne: bool = True,
) -> None:
    """Procesa embeddings para una dimensión específica."""
    print(f"\n{'=' * 80}")
    print(f"PROCESANDO DIMENSIÓN: {dimensions}")
    print(f"{'=' * 80}")
    
    # Entrenar modelo
    modelo = entrenar_node2vec(grafo, dimensions=dimensions)
    print(f"   [OK] Modelo Node2Vec entrenado")
    print(f"   - Vocabulario: {len(modelo.wv)} nodos")
    print(f"   - Dimensiones: {modelo.wv.vector_size}")
    
    # Obtener embeddings
    embeddings_dict, matriz = obtener_embeddings_completos(ontologia, modelo)
    aspectos = sorted(ontologia.keys())
    
    print(f"\n   [OK] Embeddings generados:")
    print(f"   - Aspectos: {len(embeddings_dict)}")
    print(f"   - Forma de la matriz: {matriz.shape}")
    
    # Crear directorio para esta dimensión
    dim_dir = output_dir / f"dim_{dimensions}"
    dim_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar visualizaciones y estadísticas
    visualizar_matriz_embeddings(matriz, aspectos, dimensions, dim_dir)
    visualizar_similitudes(embeddings_dict, dimensions, dim_dir)
    generar_estadisticas_embeddings(embeddings_dict, matriz, dimensions, dim_dir)
    
    if generar_pca:
        visualizar_pca(matriz, aspectos, dimensions, dim_dir)
    
    if generar_tsne:
        visualizar_tsne(matriz, aspectos, dimensions, dim_dir)
    
    print(f"\n   [OK] Procesamiento completado para {dimensions} dimensiones")
    print(f"   [OK] Resultados guardados en: {dim_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera y visualiza embeddings del grafo con diferentes dimensionalidades."
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        default=[128, 200, 300],
        help="Lista de dimensiones a probar (default: 128 200 300).",
    )
    parser.add_argument(
        "--ontology-json",
        type=str,
        default=str(Path(EXPORT_DIR) / "ontology_aspects.json"),
        help="Ruta al JSON de ontología exportado por skos_builder.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(EXPORT_DIR) / "test_embeddings"),
        help="Directorio de salida para los resultados.",
    )
    parser.add_argument(
        "--no-pca",
        action="store_true",
        help="No generar visualización PCA.",
    )
    parser.add_argument(
        "--no-tsne",
        action="store_true",
        help="No generar visualización t-SNE.",
    )
    
    args = parser.parse_args()
    
    # Cargar ontología
    print("=" * 80)
    print("CARGANDO ONTOLOGÍA")
    print("=" * 80)
    print(f"\n   -> Cargando desde: {args.ontology_json}")
    
    ontology_raw = load_ontology_from_json(args.ontology_json)
    ontologia = ontology_raw["ontologia_aspectos"]
    relaciones = ontology_raw["relaciones_aspectos"]
    
    print(f"   [OK] Ontología cargada:")
    print(f"   - Aspectos: {len(ontologia)}")
    print(f"   - Relaciones: {len(relaciones)}")
    
    # Construir grafo
    print(f"\n{'=' * 80}")
    print("CONSTRUYENDO GRAFO")
    print(f"{'=' * 80}")
    grafo = construir_grafo_conocimiento(ontologia, relaciones)
    print(f"\n   [OK] Grafo construido:")
    print(f"   - Nodos: {grafo.number_of_nodes()}")
    print(f"   - Aristas: {grafo.number_of_edges()}")
    
    # Crear directorio de salida
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Procesar cada dimensión
    for dim in args.dimensions:
        try:
            procesar_dimension(
                dimensions=dim,
                grafo=grafo,
                ontologia=ontologia,
                output_dir=output_dir,
                generar_pca=not args.no_pca,
                generar_tsne=not args.no_tsne,
            )
        except Exception as exc:
            print(f"\n   [ERROR] Error procesando dimensión {dim}: {exc}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'=' * 80}")
    print("PROCESO COMPLETADO")
    print(f"{'=' * 80}")
    print(f"\n   [OK] Todos los resultados guardados en: {output_dir}")
    print(f"\n   Archivos generados por dimensión (ejemplo para 128D):")
    print(f"   - matriz_embeddings_128d.csv: Matriz completa de embeddings")
    print(f"   - heatmap_embeddings_128d.png: Visualización de la matriz")
    print(f"   - matriz_similitudes_128d.csv: Matriz de similitudes coseno")
    print(f"   - similitudes_128d.png: Heatmap de similitudes")
    print(f"   - estadisticas_embeddings_128d.json: Estadísticas descriptivas")
    print(f"   - estadisticas_resumen_128d.csv: Tabla de estadísticas")
    if not args.no_pca:
        print(f"   - pca_coordenadas_128d.csv: Coordenadas PCA")
        print(f"   - pca_visualizacion_128d.png: Visualización PCA 2D")
    if not args.no_tsne:
        print(f"   - tsne_coordenadas_128d.csv: Coordenadas t-SNE")
        print(f"   - tsne_visualizacion_128d.png: Visualización t-SNE 2D")
    print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()

