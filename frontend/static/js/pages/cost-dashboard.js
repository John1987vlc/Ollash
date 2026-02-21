/**
 * Cost Module for Ollash Agent
 * Real-time token usage and cost visualization using Chart.js.
 */
window.CostModule = (function() {
    let container, modelChart, latencyChart, eventSource;
    let latencyData = [];
    const maxLatencyPoints = 50;

    function init() {
        container = document.getElementById('cost-dashboard-container');
        if (!container) return;

        container.innerHTML = `
            <div class="cost-dashboard">
                <div class="cost-summary" id="cost-summary">
                    <div class="cost-card">
                        <h4>Total Tokens</h4>
                        <span id="total-tokens">0</span>
                    </div>
                    <div class="cost-card">
                        <h4>Avg Latency</h4>
                        <span id="avg-latency">0ms</span>
                    </div>
                    <div class="cost-card">
                        <h4>Models Used</h4>
                        <span id="models-count">0</span>
                    </div>
                </div>
                <div class="cost-charts">
                    <div class="chart-container">
                        <h4>Tokens by Model</h4>
                        <canvas id="model-chart"></canvas>
                    </div>
                    <div class="chart-container">
                        <h4>Latency (Real-time)</h4>
                        <canvas id="latency-chart"></canvas>
                    </div>
                </div>
                <div class="cost-table" id="phase-costs-table">
                    <h4>Top Phases by Token Usage</h4>
                    <table>
                        <thead>
                            <tr><th>Phase</th><th>Tokens</th><th>Latency</th></tr>
                        </thead>
                        <tbody id="phase-costs-body"></tbody>
                    </table>
                </div>
            </div>
        `;

        loadReport();
        startSSE();
        console.log("🚀 CostModule initialized");
    }

    async function loadReport() {
        try {
            const resp = await fetch('/api/costs/report');
            const data = await resp.json();

            if (data.report) {
                updateSummary(data.report);
                renderModelChart(data.report);
                renderPhaseTable(data.report);
            }
        } catch (err) {
            console.debug('Cost report not available:', err);
        }
    }

    function updateSummary(report) {
        const totalTokensEl = document.getElementById('total-tokens');
        const avgLatencyEl = document.getElementById('avg-latency');
        const modelsCountEl = document.getElementById('models-count');

        if (totalTokensEl) totalTokensEl.textContent = formatNumber(report.total_tokens || 0);
        if (avgLatencyEl) avgLatencyEl.textContent = `${Math.round(report.avg_latency_ms || 0)}ms`;
        if (modelsCountEl) modelsCountEl.textContent = Object.keys(report.by_model || {}).length;
    }

    function renderModelChart(report) {
        const canvas = document.getElementById('model-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        const byModel = report.by_model || {};
        const labels = Object.keys(byModel);
        const data = labels.map(m => byModel[m].total_tokens || 0);

        const colors = ['#4285f4', '#34a853', '#fbbc04', '#ea4335', '#8ab4f8', '#81c995', '#fdd663', '#f28b82'];

        if (modelChart) modelChart.destroy();

        modelChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Tokens',
                    data: data,
                    backgroundColor: colors.slice(0, labels.length),
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#888' } },
                    x: { ticks: { color: '#888' } },
                },
            },
        });
    }

    function renderLatencyChart() {
        const canvas = document.getElementById('latency-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        if (latencyChart) latencyChart.destroy();

        latencyChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: latencyData.map((_, i) => i + 1),
                datasets: [{
                    label: 'Latency (ms)',
                    data: latencyData,
                    borderColor: '#8ab4f8',
                    backgroundColor: 'rgba(138,180,248,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#888' } },
                    x: { display: false },
                },
            },
        });
    }

    function renderPhaseTable(report) {
        const tbody = document.getElementById('phase-costs-body');
        if (!tbody) return;

        const byPhase = report.by_phase || {};
        const phases = Object.entries(byPhase)
            .sort((a, b) => (b[1].total_tokens || 0) - (a[1].total_tokens || 0))
            .slice(0, 5);

        tbody.innerHTML = phases.map(([phase, data]) => `
            <tr>
                <td>${phase}</td>
                <td>${formatNumber(data.total_tokens || 0)}</td>
                <td>${Math.round(data.avg_latency_ms || 0)}ms</td>
            </tr>
        `).join('');
    }

    function startSSE() {
        try {
            if (eventSource) eventSource.close();
            eventSource = new EventSource('/api/costs/stream');

            eventSource.addEventListener('cost_update', (event) => {
                const data = JSON.parse(event.data);
                handleCostUpdate(data);
            });

            eventSource.onerror = () => {
                eventSource.close();
                setTimeout(startSSE, 5000);
            };
        } catch (err) {
            console.debug('Cost SSE not available:', err);
        }
    }

    function handleCostUpdate(data) {
        if (data.latency_ms) {
            latencyData.push(data.latency_ms);
            if (latencyData.length > maxLatencyPoints) latencyData.shift();
            renderLatencyChart();
        }
        const totalTokensEl = document.getElementById('total-tokens');
        if (totalTokensEl && data.total_tokens) {
            totalTokensEl.textContent = formatNumber(data.total_tokens);
        }
    }

    function formatNumber(n) {
        if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
        if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
        return String(n);
    }

    return {
        init: init,
        updateCostsDashboard: loadReport
    };
})();
