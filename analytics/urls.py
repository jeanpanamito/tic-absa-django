"""
Analytics URL configuration.

Template views serve the HTML shells; API views return JSON data
consumed by the frontend JavaScript via fetch().
"""

from django.urls import path
from . import views, api_views

app_name = 'analytics'

urlpatterns = [
    # ─── Template Views (HTML pages) ────────────────
    path('', views.overview, name='overview'),
    path('detailed/', views.detailed, name='detailed'),
    path('graph/', views.graph, name='graph'),
    path('rag/', views.rag, name='rag'),

    # ─── API: Overview data ─────────────────────────
    path('api/stats/', api_views.general_stats, name='api_stats'),
    path('api/polarity/', api_views.polarity_distribution, name='api_polarity'),
    path('api/aspects/', api_views.aspect_distribution, name='api_aspects'),
    path('api/heatmap/', api_views.sentiment_heatmap, name='api_heatmap'),

    # ─── API: Detailed analysis ─────────────────────
    path('api/top-negative/', api_views.top_negative, name='api_top_negative'),
    path('api/course-ranking/', api_views.course_ranking, name='api_course_ranking'),
    path('api/confidence/', api_views.confidence_distribution, name='api_confidence'),
    path('api/comments/', api_views.filtered_comments, name='api_comments'),

    # ─── API: Graph visualization ───────────────────
    path('api/graph-data/', api_views.graph_data, name='api_graph_data'),

    # ─── API: Filters / options ─────────────────────
    path('api/available-aspects/', api_views.available_aspects, name='api_available_aspects'),
    path('api/available-courses/', api_views.available_courses, name='api_available_courses'),

    # ─── API: RAG ───────────────────────────────────
    path('api/rag/query/', api_views.rag_query, name='api_rag_query'),
    path('api/rag/report/', api_views.rag_report, name='api_rag_report'),
]
