"""
API views — JSON endpoints consumed by the frontend JavaScript.

All GET endpoints return data for charts/tables.
POST endpoints handle RAG queries and report generation.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from .services.neo4j_service import Neo4jService
from .services.rag_service import RAGService

logger = logging.getLogger('analytics.api')


def _error_response(message: str, status: int = 500) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _get_neo4j() -> Neo4jService:
    svc = Neo4jService()
    if not svc.is_connected:
        raise ConnectionError("Neo4j no está conectado.")
    return svc


# ──────────────────────────────────────────────────
# Overview endpoints
# ──────────────────────────────────────────────────

@require_GET
def general_stats(request):
    """GET /api/stats/ → KPI numbers."""
    try:
        svc = _get_neo4j()
        return JsonResponse(svc.get_general_statistics())
    except Exception as e:
        logger.exception("Error fetching stats")
        return _error_response(str(e))


@require_GET
def polarity_distribution(request):
    """GET /api/polarity/ → [{polarity, count}, ...]"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_polarity_distribution()})
    except Exception as e:
        logger.exception("Error fetching polarity")
        return _error_response(str(e))


@require_GET
def aspect_distribution(request):
    """GET /api/aspects/ → [{aspect, count}, ...]"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_aspect_distribution()})
    except Exception as e:
        logger.exception("Error fetching aspects")
        return _error_response(str(e))


@require_GET
def sentiment_heatmap(request):
    """GET /api/heatmap/ → [{aspect, sentiment, count}, ...]"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_sentiment_heatmap()})
    except Exception as e:
        logger.exception("Error fetching heatmap")
        return _error_response(str(e))


# ──────────────────────────────────────────────────
# Detailed analysis endpoints
# ──────────────────────────────────────────────────

@require_GET
def top_negative(request):
    """GET /api/top-negative/?limit=10"""
    try:
        svc = _get_neo4j()
        limit = int(request.GET.get('limit', 10))
        return JsonResponse({"data": svc.get_top_negative_aspects(limit=limit)})
    except Exception as e:
        logger.exception("Error fetching top negative")
        return _error_response(str(e))


@require_GET
def course_ranking(request):
    """GET /api/course-ranking/"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_course_sentiment_ranking()})
    except Exception as e:
        logger.exception("Error fetching course ranking")
        return _error_response(str(e))


@require_GET
def confidence_distribution(request):
    """GET /api/confidence/"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_confidence_distribution()})
    except Exception as e:
        logger.exception("Error fetching confidence")
        return _error_response(str(e))


@require_GET
def filtered_comments(request):
    """GET /api/comments/?aspects=a1,a2&min_confidence=0.5&polarities=Negativo"""
    try:
        svc = _get_neo4j()

        aspects_param = request.GET.get('aspects', '')
        aspects = [a.strip() for a in aspects_param.split(',') if a.strip()] or None

        polarities_param = request.GET.get('polarities', '')
        polarities = [p.strip() for p in polarities_param.split(',') if p.strip()] or None

        min_conf = float(request.GET.get('min_confidence', 0.0))

        data = svc.get_filtered_comments(
            aspects=aspects,
            polarities=polarities,
            min_confidence=min_conf,
        )
        return JsonResponse({"data": data, "count": len(data)})
    except Exception as e:
        logger.exception("Error fetching comments")
        return _error_response(str(e))


# ──────────────────────────────────────────────────
# Graph visualization endpoint
# ──────────────────────────────────────────────────

@require_GET
def graph_data(request):
    """GET /api/graph-data/?max_nodes=50&focus_aspect=Evaluaciones"""
    try:
        svc = _get_neo4j()
        max_nodes = int(request.GET.get('max_nodes', 50))
        focus_aspect = request.GET.get('focus_aspect') or None
        data = svc.get_graph_data(max_nodes=max_nodes, focus_aspect=focus_aspect)
        return JsonResponse(data)
    except Exception as e:
        logger.exception("Error fetching graph data")
        return _error_response(str(e))


# ──────────────────────────────────────────────────
# Filter options endpoints
# ──────────────────────────────────────────────────

@require_GET
def available_aspects(request):
    """GET /api/available-aspects/"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_available_aspects()})
    except Exception as e:
        logger.exception("Error fetching aspects list")
        return _error_response(str(e))


@require_GET
def available_courses(request):
    """GET /api/available-courses/"""
    try:
        svc = _get_neo4j()
        return JsonResponse({"data": svc.get_available_courses()})
    except Exception as e:
        logger.exception("Error fetching courses list")
        return _error_response(str(e))


# ──────────────────────────────────────────────────
# RAG endpoints (POST with JSON body)
# ──────────────────────────────────────────────────

@csrf_exempt
@require_POST
def rag_query(request):
    """
    POST /api/rag/query/
    Body: {"question": "...", "course_filter": "..." | null}
    """
    try:
        svc = RAGService()
        if not svc.is_available:
            return _error_response(
                "El motor RAG no está disponible. Verifica OPENAI_API_KEY.", 503
            )

        body = json.loads(request.body)
        question = body.get('question', '').strip()
        if not question:
            return _error_response("La pregunta no puede estar vacía.", 400)

        course_filter = body.get('course_filter') or None
        answer = svc.query(question, course_filter=course_filter)
        return JsonResponse({"answer": answer})
    except json.JSONDecodeError:
        return _error_response("JSON inválido.", 400)
    except Exception as e:
        logger.exception("RAG query error")
        return _error_response(str(e))


@csrf_exempt
@require_POST
def rag_report(request):
    """
    POST /api/rag/report/
    Body: {"course_id": "..."}
    """
    try:
        svc = RAGService()
        if not svc.is_available:
            return _error_response(
                "El motor RAG no está disponible. Verifica OPENAI_API_KEY.", 503
            )

        body = json.loads(request.body)
        course_id = body.get('course_id', '').strip()
        if not course_id:
            return _error_response("course_id es requerido.", 400)

        report = svc.get_course_report(course_id)
        return JsonResponse({"report": report})
    except json.JSONDecodeError:
        return _error_response("JSON inválido.", 400)
    except Exception as e:
        logger.exception("RAG report error")
        return _error_response(str(e))
