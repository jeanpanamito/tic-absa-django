/**
 * charts.js — Shared Plotly utility functions
 * Currently the chart logic is inlined in each template for simplicity.
 * This file provides reusable helpers.
 */

// Dark theme defaults for all Plotly charts
const PLOTLY_DARK_LAYOUT = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {
        color: '#9ca3af',
        family: 'Inter, sans-serif',
        size: 12,
    },
    margin: { t: 30, b: 40, l: 60, r: 20 },
};

const PLOTLY_CONFIG = {
    displayModeBar: false,
    responsive: true,
};

// Polarity color map
const POLARITY_COLORS = {
    'Positivo': '#10b981',
    'Negativo': '#ef4444',
    'Neutral':  '#6b7280',
};

/**
 * Animate a number counter from 0 to target.
 */
function animateCounter(elementId, target, duration = 800) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const start = performance.now();
    const format = (n) => n.toLocaleString('es-EC');

    function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = format(Math.floor(target * eased));
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

/**
 * Show an error message inside a chart container.
 */
function showChartError(containerId, message = 'Error cargando datos') {
    const el = document.getElementById(containerId);
    if (el) {
        el.innerHTML = `<div class="flex items-center justify-center h-full text-gray-500 text-sm">${message}</div>`;
    }
}
