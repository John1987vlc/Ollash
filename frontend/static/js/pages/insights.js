/**
 * Analytics & Insights Page Logic
 * Extracted from insights.html inline script.
 */
(function () {
    let currentReportId = null;

    async function fetchInsights() {
        try {
            const res = await fetch('/api/reports/weekly');
            const data = await res.json();

            if (data.error) throw new Error(data.error);

            currentReportId = data.id;

            document.getElementById('report-title').textContent = data.title;
            document.getElementById('report-summary-text').textContent = data.summary;
            document.getElementById('performance-score').textContent = Math.round(data.performance_score);

            const loc = data.metrics.find(m => m.name === 'Lines Of Code Generated');
            const fixed = data.metrics.find(m => m.name === 'Auto Corrected Errors');
            const time = data.metrics.find(m => m.name === 'Time Saved Hours');

            if (loc) document.getElementById('metric-loc').textContent = loc.value;
            if (fixed) document.getElementById('metric-fixed').textContent = fixed.value;
            if (time) document.getElementById('metric-time').textContent = time.value + 'h';

            const recList = document.getElementById('recommendations-list');
            if (recList) {
                recList.innerHTML = '';
                data.recommendations.forEach(rec => {
                    const item = document.createElement('div');
                    item.className = 'recommendation-item';
                    item.textContent = rec;
                    recList.appendChild(item);
                });
            }

            initTrendChart(data.trends);

        } catch (error) {
            console.error('Error fetching insights:', error);
            const title = document.getElementById('report-title');
            if (title) title.textContent = 'Error Generating Report';
        }
    }

    function initTrendChart(trends) {
        const canvas = document.getElementById('trendsChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const ctx = canvas.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Productivity Score',
                    data: trends || [65, 78, 82, 75, 90, 85, 94],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a1a1aa' } },
                    x: { grid: { display: false }, ticks: { color: '#a1a1aa' } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        fetchInsights();

        document.getElementById('export-md-btn')?.addEventListener('click', () => {
            if (currentReportId) {
                window.location.href = `/api/reports/export/${currentReportId}?format=markdown`;
            }
        });

        document.getElementById('export-html-btn')?.addEventListener('click', () => {
            if (currentReportId) {
                window.location.href = `/api/reports/export/${currentReportId}?format=html`;
            }
        });
    });
}());
