"""
Template views — each renders an HTML shell that loads data via JS fetch().
"""

from django.shortcuts import render


def overview(request):
    """Dashboard overview: KPIs, polarity pie, aspect bars, sentiment heatmap."""
    return render(request, 'analytics/overview.html')


def detailed(request):
    """Detailed analysis: top complaints, course ranking, confidence, data explorer."""
    return render(request, 'analytics/detailed.html')


def graph(request):
    """Knowledge graph visualization powered by Vis.js."""
    return render(request, 'analytics/graph.html')


def rag(request):
    """RAG chat interface and executive report generator."""
    return render(request, 'analytics/rag.html')
