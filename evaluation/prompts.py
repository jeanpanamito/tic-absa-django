#!/usr/bin/env python3
"""
Shared prompts for the ABSA experiment layer.

SINGLE SOURCE OF TRUTH — all prompts used in Phases A–C are defined here.
Never hardcode prompts in individual scripts; always import from this module.

The ABSA prompt is copied verbatim from absa/semantic_pipeline.py (L322-L353).
The Judge prompt is copied verbatim from evaluation/validate_neo4j.py (L89-L110).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# ABSA System Prompt — verbatim from absa/semantic_pipeline.py L322-L334
# ---------------------------------------------------------------------------

ABSA_SYSTEM_PROMPT: str = (
    "Eres un asistente experto en análisis de sentimientos basado en aspectos "
    "(ABSA) para comentarios de foros educativos.\n"
    "\n"
    "Tu tarea es:\n"
    "1. Identificar todos los aspectos educativos mencionados en el comentario\n"
    "2. Usar ÚNICAMENTE los aspectos de la ontología proporcionada\n"
    "3. Determinar el sentimiento (Positivo, Negativo o Neutral) para cada aspecto\n"
    "4. Extraer la frase exacta que justifica tu análisis\n"
    "\n"
    "IMPORTANTE:\n"
    "- Mapea términos informales a conceptos formales "
    '(ej: "test", "examen" -> "Evaluacion")\n'
    "- Considera las relevancia semántica indicadas en los aspectos\n"
    "- Un comentario puede tener múltiples aspectos con diferentes sentimientos\n"
    "- Responde SOLO con JSON válido sin texto adicional"
)


# ---------------------------------------------------------------------------
# Judge System Prompt — verbatim from evaluation/validate_neo4j.py L89-L100
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT: str = (
    "Eres un experto lingüista evaluando un sistema de Análisis de Sentimientos "
    "Basado en Aspectos (ABSA) para el dominio educativo.\n"
    "Tu tarea es validar si el sistema ha extraído correctamente el aspecto y el "
    "sentimiento de un comentario de un estudiante.\n"
    "\n"
    "Responde ÚNICAMENTE en formato JSON con la siguiente estructura:\n"
    "{\n"
    '    "relevancia_aspecto": <int 1-5, donde 1 es totalmente irrelevante/'
    "alucinación y 5 es explícito y correcto>,\n"
    '    "aspecto_correcto": <bool, true si el aspecto extraído corresponde '
    "razonablemente al texto, aunque sea implícito>,\n"
    '    "sentimiento_correcto": <bool, true si la polaridad '
    "(Positivo/Negativo/Neutral) es correcta dada la mención>,\n"
    '    "sentimiento_real": <str, "Positivo", "Negativo" o "Neutral", '
    "tu juicio experto>,\n"
    '    "explicacion": <str, breve justificación en español>\n'
    "}"
)


# ---------------------------------------------------------------------------
# Cosine–similarity threshold for candidate guide injection
# ---------------------------------------------------------------------------

COSINE_HIGH_THRESHOLD: float = 0.40
COSINE_MED_THRESHOLD: float = 0.25


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_aspect_lines(
    ontologia: Dict[str, Dict[str, Optional[str]]],
    similitudes: Optional[Dict[str, float]],
) -> List[str]:
    """Build the hierarchical aspect list with optional relevance markers.

    Reproduces the logic from semantic_pipeline.py L304-L320.
    """
    lines: List[str] = []
    for aspecto, info in ontologia.items():
        aspecto_str = f"   - {aspecto}"
        padre = info.get("padre")
        if padre:
            aspecto_str += f" (subcategoría de {padre})"
        descripcion = info.get("descripcion")
        if descripcion:
            aspecto_str += f": {descripcion}"

        if similitudes and aspecto in similitudes:
            sim = similitudes[aspecto]
            if sim > COSINE_HIGH_THRESHOLD:
                aspecto_str = (
                    f"*** {aspecto_str} [ALTA RELEVANCIA: {sim:.2f}] ***"
                )
            elif sim > COSINE_MED_THRESHOLD:
                aspecto_str += f" [Relevancia: {sim:.2f}]"

        lines.append(aspecto_str)
    return lines


def build_absa_user_prompt(
    comment_text: str,
    ontologia: Dict[str, Dict[str, Optional[str]]],
    similitudes: Optional[Dict[str, float]],
) -> str:
    """Reconstruct the exact user prompt from semantic_pipeline.py L336-L353.

    Args:
        comment_text: The raw comment text.
        ontologia: The SKOS aspect ontology dict.
        similitudes: Per-aspect cosine similarities (or ``None`` for no-guides).

    Returns:
        The formatted user prompt string.
    """
    aspect_lines = _build_aspect_lines(ontologia, similitudes)

    user_prompt = (
        f"**ONTOLOGÍA DE ASPECTOS:**\n"
        f"{os.linesep.join(aspect_lines)}\n"
        f"\n"
        f"**COMENTARIO:**\n"
        f'"{comment_text}"\n'
        f"\n"
        f"**FORMATO JSON (SOLO ESTE FORMATO):**\n"
        f"{{\n"
        f'  "aspectos": [\n'
        f"    {{\n"
        f'      "aspecto_oficial": "<nombre exacto del aspecto>",\n'
        f'      "sentimiento": "<Positivo|Negativo|Neutral>",\n'
        f'      "mencion_original": "<frase del texto>",\n'
        f'      "justificacion": "<explicación breve>",\n'
        f'      "confianza": <0.0-1.0>\n'
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )
    return user_prompt


def build_absa_user_prompt_no_guides(
    comment_text: str,
    ontologia: Dict[str, Dict[str, Optional[str]]],
) -> str:
    """Build the ABSA user prompt **without** cosine similarity guides.

    This is the ablation variant (Phase A3): the ontology is listed but no
    ``*** ALTA RELEVANCIA ***`` markers are injected.
    """
    return build_absa_user_prompt(comment_text, ontologia, similitudes=None)


def build_judge_user_prompt(
    text: str,
    aspect: str,
    sentiment: str,
) -> str:
    """Reconstruct the judge user prompt from validate_neo4j.py L102-L110.

    Args:
        text: The original comment text.
        aspect: The aspect predicted by the ABSA system.
        sentiment: The sentiment predicted by the ABSA system.

    Returns:
        The formatted judge user prompt string.
    """
    return (
        f'\n    COMENTARIO: "{text}"\n'
        f"\n"
        f"    EXTRACCIÓN DEL SISTEMA:\n"
        f'    - Aspecto Detectado: "{aspect}"\n'
        f'    - Sentimiento Detectado: "{sentiment}"\n'
        f"\n"
        f"    Evalúa la calidad de esta extracción.\n"
        f"    "
    )
