/**
 * Analytics Dashboard — P10 Metacognition
 *
 * Fetches data from /api/analytics/* and renders Chart.js charts plus
 * interactive node/lessons tables.
 */
(function AnalyticsDashboard() {
    'use strict';

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    function fmt(n) {
        if (n === undefined || n === null || n === '--') return '--';
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k';
        return String(n);
    }

    function fmtMs(ms) {
        if (!ms) return '—';
        if (ms >= 60_000) return (ms / 60_000).toFixed(1) + 'm';
        if (ms >= 1_000) return (ms / 1_000).toFixed(1) + 's';
        return ms + 'ms';
    }

    function fmtDate(iso) {
        if (!iso) return '—';
        try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
    }

    function agentBadge(type) {
        const cls = 'badge-' + (type || 'unknown').toLowerCase().replace(/[^a-z]/g, '');
        return `<span class="${cls}">${type || '?'}</span>`;
    }

    async function fetchJson(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${url} → ${r.status}`);
        return r.json();
    }

    // -------------------------------------------------------------------------
    // Chart instances (kept for destroy on re-render)
    // -------------------------------------------------------------------------

    let _chartTokens = null;
    let _chartAgents = null;

    function destroyCharts() {
        if (_chartTokens) { _chartTokens.destroy(); _chartTokens = null; }
        if (_chartAgents) { _chartAgents.destroy(); _chartAgents = null; }
    }

    // -------------------------------------------------------------------------
    // Render KPI summary
    // -------------------------------------------------------------------------

    async function loadSummary() {
        try {
            const data = await fetchJson('/api/analytics/summary');
            document.getElementById('kpi-projects').textContent = fmt(data.total_projects);
            document.getElementById('kpi-tokens').textContent   = fmt(data.total_tokens);
            document.getElementById('kpi-files').textContent    = fmt(data.total_files);
            document.getElementById('kpi-failed').textContent   = fmt(data.total_failed);
            return data;
        } catch {
            return {};
        }
    }

    // -------------------------------------------------------------------------
    // Render charts
    // -------------------------------------------------------------------------

    function renderTokensChart(projects) {
        const recent = projects.slice(0, 10).reverse();
        const labels = recent.map(p => p.project_name || 'unnamed');
        const values = recent.map(p => p.total_tokens || 0);

        const ctx = document.getElementById('chart-tokens-per-project');
        if (!ctx) return;

        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';
        const textColor = isDark ? '#a0aec0' : '#4a5568';

        _chartTokens = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Tokens',
                    data: values,
                    backgroundColor: 'rgba(99,102,241,0.7)',
                    borderColor: 'rgba(99,102,241,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: textColor, maxRotation: 30 }, grid: { color: gridColor } },
                    y: { ticks: { color: textColor, callback: v => fmt(v) }, grid: { color: gridColor } },
                }
            }
        });
    }

    function renderAgentChart(summary) {
        const counts = summary.agent_type_counts || {};
        const labels = Object.keys(counts);
        const values = Object.values(counts);

        const ctx = document.getElementById('chart-agent-types');
        if (!ctx || !labels.length) return;

        const COLORS = {
            DEVELOPER: '#3b82f6',
            DEVOPS:    '#a855f7',
            AUDITOR:   '#f59e0b',
            ARCHITECT: '#22c55e',
            DEBATE:    '#ec4899',
        };
        const bgColors = labels.map(l => COLORS[l] || '#6b7280');

        _chartAgents = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: bgColors,
                    borderWidth: 2,
                    borderColor: 'transparent',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // Project selector + node breakdown
    // -------------------------------------------------------------------------

    async function loadProjects() {
        let projects = [];
        try {
            projects = await fetchJson('/api/analytics/projects');
        } catch {
            return projects;
        }
        const sel = document.getElementById('analytics-project-select');
        if (!sel) return projects;

        // Populate dropdown
        sel.innerHTML = '<option value="">— Select project —</option>';
        for (const p of projects) {
            const opt = document.createElement('option');
            opt.value = p.project_name;
            opt.textContent = `${p.project_name} (${fmtDate(p.timestamp)})`;
            sel.appendChild(opt);
        }
        return projects;
    }

    async function loadNodeDetail(projectName) {
        const tbody = document.getElementById('analytics-node-tbody');
        if (!tbody) return;

        if (!projectName) {
            tbody.innerHTML = '<tr><td colspan="5" class="analytics-empty">Select a project to view details.</td></tr>';
            return;
        }

        tbody.innerHTML = '<tr><td colspan="5" class="analytics-empty">Loading…</td></tr>';
        try {
            const nodes = await fetchJson(`/api/analytics/projects/${encodeURIComponent(projectName)}`);
            if (!nodes.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="analytics-empty">No node records found.</td></tr>';
                return;
            }
            tbody.innerHTML = nodes.map(n => `
                <tr>
                    <td title="${n.task_id}">${n.task_id || '—'}</td>
                    <td>${agentBadge(n.agent_type)}</td>
                    <td>${fmtMs(n.duration_ms)}</td>
                    <td>${fmt(n.tokens)}</td>
                    <td>${n.retry_count || 0}</td>
                </tr>
            `).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5" class="analytics-empty">Error: ${err.message}</td></tr>`;
        }
    }

    // -------------------------------------------------------------------------
    // Lessons Learned
    // -------------------------------------------------------------------------

    async function loadLessons() {
        const tbody = document.getElementById('analytics-lessons-tbody');
        if (!tbody) return;

        try {
            const lessons = await fetchJson('/api/analytics/lessons');
            if (!lessons.length) {
                tbody.innerHTML = '<tr><td colspan="4" class="analytics-empty">No lessons recorded yet.</td></tr>';
                return;
            }
            tbody.innerHTML = lessons.map(l => `
                <tr>
                    <td>${fmtDate(l.date)}</td>
                    <td>${agentBadge(l.agent)}</td>
                    <td>${l.error_pattern || '—'}</td>
                    <td>${l.fix_applied || '—'}</td>
                </tr>
            `).join('');
        } catch {
            tbody.innerHTML = '<tr><td colspan="4" class="analytics-empty">Could not load lessons.</td></tr>';
        }
    }

    // -------------------------------------------------------------------------
    // Init
    // -------------------------------------------------------------------------

    async function init() {
        destroyCharts();

        const [summary, projects] = await Promise.all([loadSummary(), loadProjects()]);

        renderTokensChart(projects);
        renderAgentChart(summary);
        loadLessons();

        // Node detail on project selection
        const sel = document.getElementById('analytics-project-select');
        if (sel) {
            sel.addEventListener('change', () => loadNodeDetail(sel.value));
        }

        // Refresh button
        const btn = document.getElementById('analytics-refresh-btn');
        if (btn) {
            btn.addEventListener('click', init);
        }
    }

    // Expose init so main.js can call it when the view becomes active
    window.AnalyticsDashboard = { init };
})();
