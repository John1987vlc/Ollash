/**
 * Cost Dashboard (F8)
 * Real-time token usage and cost visualization using Chart.js.
 */

class CostDashboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.modelChart = null;
        this.latencyChart = null;
        this.eventSource = null;
        this.latencyData = [];
        this.maxLatencyPoints = 50;
    }

    async init() {
        if (!this.container) return;

        this.container.innerHTML = `
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

        await this.loadReport();
        this._startSSE();
    }

    async loadReport() {
        try {
            const resp = await fetch('/api/costs/report');
            const data = await resp.json();

            if (data.report) {
                this._updateSummary(data.report);
                this._renderModelChart(data.report);
                this._renderPhaseTable(data.report);
            }
        } catch (err) {
            console.debug('Cost report not available:', err);
        }
    }

    _updateSummary(report) {
        const totalTokensEl = document.getElementById('total-tokens');
        const avgLatencyEl = document.getElementById('avg-latency');
        const modelsCountEl = document.getElementById('models-count');

        if (totalTokensEl) {
            totalTokensEl.textContent = this._formatNumber(report.total_tokens || 0);
        }
        if (avgLatencyEl) {
            avgLatencyEl.textContent = `${Math.round(report.avg_latency_ms || 0)}ms`;
        }
        if (modelsCountEl) {
            modelsCountEl.textContent = Object.keys(report.by_model || {}).length;
        }
    }

    _renderModelChart(report) {
        const canvas = document.getElementById('model-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        const byModel = report.by_model || {};
        const labels = Object.keys(byModel);
        const data = labels.map(m => byModel[m].total_tokens || 0);

        const colors = [
            '#4285f4', '#34a853', '#fbbc04', '#ea4335',
            '#8ab4f8', '#81c995', '#fdd663', '#f28b82',
        ];

        if (this.modelChart) this.modelChart.destroy();

        this.modelChart = new Chart(canvas, {
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
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#888' } },
                    x: { ticks: { color: '#888' } },
                },
            },
        });
    }

    _renderLatencyChart() {
        const canvas = document.getElementById('latency-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        if (this.latencyChart) this.latencyChart.destroy();

        this.latencyChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: this.latencyData.map((_, i) => i + 1),
                datasets: [{
                    label: 'Latency (ms)',
                    data: this.latencyData,
                    borderColor: '#8ab4f8',
                    backgroundColor: 'rgba(138,180,248,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                }],
            },
            options: {
                responsive: true,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#888' } },
                    x: { display: false },
                },
            },
        });
    }

    _renderPhaseTable(report) {
        const tbody = document.getElementById('phase-costs-body');
        if (!tbody) return;

        const byPhase = report.by_phase || {};
        const phases = Object.entries(byPhase)
            .sort((a, b) => (b[1].total_tokens || 0) - (a[1].total_tokens || 0))
            .slice(0, 5);

        tbody.innerHTML = phases.map(([phase, data]) => `
            <tr>
                <td>${phase}</td>
                <td>${this._formatNumber(data.total_tokens || 0)}</td>
                <td>${Math.round(data.avg_latency_ms || 0)}ms</td>
            </tr>
        `).join('');
    }

    _startSSE() {
        try {
            this.eventSource = new EventSource('/api/costs/stream');

            this.eventSource.addEventListener('cost_update', (event) => {
                const data = JSON.parse(event.data);
                this._handleCostUpdate(data);
            });

            this.eventSource.onerror = () => {
                setTimeout(() => this._startSSE(), 5000);
            };
        } catch (err) {
            console.debug('Cost SSE not available:', err);
        }
    }

    _handleCostUpdate(data) {
        // Update latency chart
        if (data.latency_ms) {
            this.latencyData.push(data.latency_ms);
            if (this.latencyData.length > this.maxLatencyPoints) {
                this.latencyData.shift();
            }
            this._renderLatencyChart();
        }

        // Update total tokens
        const totalTokensEl = document.getElementById('total-tokens');
        if (totalTokensEl && data.total_tokens) {
            totalTokensEl.textContent = this._formatNumber(data.total_tokens);
        }
    }

    _formatNumber(n) {
        if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
        if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
        return String(n);
    }

    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        if (this.modelChart) this.modelChart.destroy();
        if (this.latencyChart) this.latencyChart.destroy();
    }
}

window.CostDashboard = CostDashboard;
