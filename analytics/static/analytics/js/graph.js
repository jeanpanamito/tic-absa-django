/**
 * graph.js — Vis.js graph utilities
 * Currently the graph logic is inlined in graph.html.
 * This file provides reusable helpers for future extraction.
 */

// Vis.js default options for the ABSA knowledge graph
const VIS_DEFAULT_OPTIONS = {
    physics: {
        enabled: true,
        stabilization: { iterations: 200 },
        barnesHut: {
            gravitationalConstant: -2000,
            centralGravity: 0.1,
            springLength: 150,
            springConstant: 0.05,
            damping: 0.09,
        },
    },
    interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true,
    },
};
