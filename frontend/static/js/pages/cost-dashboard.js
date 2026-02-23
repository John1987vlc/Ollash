/**
 * Cost Module for Ollash Agent
 * Real-time token usage and cost visualization using Chart.js.
 */
window.CostModule = (function() {
    let modelChart, historyChart;

    function init() {
        if (!document.getElementById('costs-view')) {
            console.debug("CostModule: view not found");
            return;
        }

        loadReport();
        console.log("🚀 CostModule initialized");
    }

    async function loadReport() {
        try {
            const resp = await fetch('/api/costs/report');
            const data = await resp.json();

            if (data.report) {
                updateSummary(data.report);
                renderAgentChart(data.report);
                renderHistoryChart(data.report);
                renderSuggestions(data.suggestions || []);
            }
        } catch (err) {
            console.debug('Cost report not available:', err);
        }
    }

    function updateSummary(report) {
        const totalTokensEl = document.getElementById('total-tokens-val');
        const totalCostEl = document.getElementById('total-cost-val');
        const tokenSplitEl = document.getElementById('tokens-split');

        if (totalTokensEl) totalTokensEl.textContent = formatNumber(report.total_tokens || 0);
        if (totalCostEl) totalCostEl.textContent = `$${(report.total_cost || 0).toFixed(4)}`;
        if (tokenSplitEl) {
            tokenSplitEl.textContent = `Prompt: ${formatNumber(report.prompt_tokens || 0)} | Comp: ${formatNumber(report.completion_tokens || 0)}`;
        }
    }

    function renderAgentChart(report) {
        const canvas = document.getElementById('cost-agent-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        const byAgent = report.by_agent || {};
        const labels = Object.keys(byAgent);
        const data = labels.map(a => byAgent[a].total_tokens || 0);

        if (modelChart) modelChart.destroy();

        modelChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
                    borderWidth: 0
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#888', usePointStyle: true } }
                }
            },
        });
    }

    function renderHistoryChart(report) {
        const canvas = document.getElementById('token-history-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        // Mock history if not provided for visual effect
        const labels = report.history_labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const data = report.history_data || [1200, 1900, 3000, 5000, 2000, 3000, 4500];

        if (historyChart) historyChart.destroy();

        historyChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Tokens',
                    data: data,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
                    x: { grid: { display: false }, ticks: { color: '#888' } },
                },
            },
        });
    }

    function renderSuggestions(suggestions) {
        const list = document.getElementById('cost-suggestions-list');
        if (!list) return;

        if (suggestions.length === 0) {
            list.innerHTML = '<p class="placeholder">No optimization suggestions at this time.</p>';
            return;
        }

        list.innerHTML = suggestions.map(s => `
            <div class="suggestion-card">
                <div class="suggestion-icon">${s.type === 'warning' ? '⚠️' : '💡'}</div>
                <div class="suggestion-content">
                    <strong>${s.title}</strong>
                    <p>${s.message}</p>
                </div>
            </div>
        `).join('');
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
