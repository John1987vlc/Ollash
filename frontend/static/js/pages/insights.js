/**
 * Analytics & Insights Page Logic
 */
if (typeof window.loadInsightsData === 'undefined') {
    (function () {
        let currentReportId = null;
        let trendsChartInstance = null;

        async function fetchInsights() {
            try {
                const res = await fetch('/api/reports/weekly');
                const data = await res.json();

                if (data.error) throw new Error(data.error);

                currentReportId = data.id;

                const titleEl = document.getElementById('report-title');
                const summaryEl = document.getElementById('report-summary-text');
                const scoreEl = document.getElementById('performance-score');

                if (titleEl) titleEl.textContent = data.title;
                if (summaryEl) summaryEl.textContent = data.summary;
                if (scoreEl) scoreEl.textContent = Math.round(data.performance_score);

                const loc = data.metrics.find(m => m.name === 'Lines Of Code Generated');
                const fixed = data.metrics.find(m => m.name === 'Auto Corrected Errors');
                const time = data.metrics.find(m => m.name === 'Time Saved Hours');

                if (loc) {
                    const el = document.getElementById('metric-loc');
                    if (el) el.textContent = loc.value;
                }
                if (fixed) {
                    const el = document.getElementById('metric-fixed');
                    if (el) el.textContent = fixed.value;
                }
                if (time) {
                    const el = document.getElementById('metric-time');
                    if (el) el.textContent = time.value + 'h';
                }

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
            }
        }

        function initTrendChart(trends) {
            const canvas = document.getElementById('trendsChart');
            if (!canvas || typeof Chart === 'undefined') return;

            if (trendsChartInstance) {
                trendsChartInstance.destroy();
            }

            const ctx = canvas.getContext('2d');
            trendsChartInstance = new Chart(ctx, {
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

        window.loadInsightsData = fetchInsights;

        document.addEventListener('DOMContentLoaded', () => {
            if (document.getElementById('insights-view')) {
                fetchInsights();
            }

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
}
