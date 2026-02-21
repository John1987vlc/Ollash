/**
 * Benchmark Module for Ollash Agent
 */
window.BenchmarkModule = (function() {
    let benchOllamaUrl, benchFetchModels, benchModelList, benchStartBtn, benchOutput, benchHistoryList;
    let benchEventSource = null;

    function init(elements) {
        benchOllamaUrl = elements.benchOllamaUrl;
        benchFetchModels = elements.benchFetchModels;
        benchModelList = elements.benchModelList;
        benchStartBtn = elements.benchStartBtn;
        benchOutput = elements.benchOutput;
        benchHistoryList = elements.benchHistoryList;

        if (benchFetchModels) {
            benchFetchModels.addEventListener('click', fetchModels);
        }

        if (benchStartBtn) {
            benchStartBtn.addEventListener('click', startBenchmark);
        }

        loadBenchHistory();
    }

    async function fetchModels() {
        const url = benchOllamaUrl.value.trim();
        const params = url ? `?url=${encodeURIComponent(url)}` : '';
        benchModelList.innerHTML = '<div class="model-list-empty">Loading models...</div>';

        try {
            const resp = await fetch(`/api/benchmark/models${params}`);
            const data = await resp.json();

            if (data.status !== 'ok') {
                benchModelList.innerHTML = `<div class="model-list-empty" style="color:var(--color-error);">${escapeHtml(data.message)}</div>`;
                return;
            }

            if (!benchOllamaUrl.value.trim()) benchOllamaUrl.value = data.ollama_url;

            if (data.models.length === 0) {
                benchModelList.innerHTML = '<div class="model-list-empty">No models found on this server</div>';
                return;
            }

            benchModelList.innerHTML = '';
            data.models.forEach(m => {
                if (m.supports_chat === false) return; // Skip embedding models in UI
                
                const label = document.createElement('label');
                label.className = 'model-item';
                label.innerHTML = `
                    <input type="checkbox" value="${escapeHtml(m.name)}">
                    <span class="model-item-name">${escapeHtml(m.name)}</span>
                    <span class="model-item-size">${escapeHtml(m.size_human)}</span>
                `;
                label.querySelector('input').addEventListener('change', updateBenchStartBtn);
                benchModelList.appendChild(label);
            });
        } catch (err) {
            benchModelList.innerHTML = `<div class="model-list-empty" style="color:var(--color-error);">Connection error: ${escapeHtml(err.message)}</div>`;
        }
    }

    function updateBenchStartBtn() {
        const checked = benchModelList.querySelectorAll('input[type="checkbox"]:checked');
        if (benchStartBtn) benchStartBtn.disabled = checked.length === 0;
    }

    async function startBenchmark() {
        const checked = benchModelList.querySelectorAll('input[type="checkbox"]:checked');
        const models = Array.from(checked).map(cb => cb.value);
        if (models.length === 0) return;

        benchStartBtn.disabled = true;
        benchOutput.innerHTML = '<div class="bench-progress"><p>Starting benchmark...</p></div>';

        try {
            const resp = await fetch('/api/benchmark/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    models: models,
                    ollama_url: benchOllamaUrl.value.trim()
                })
            });
            const data = await resp.json();

            if (data.status !== 'started') {
                benchOutput.innerHTML = `<div class="bench-progress" style="color:var(--color-error);">${escapeHtml(data.message)}</div>`;
                benchStartBtn.disabled = false;
                return;
            }

            // Open SSE stream
            if (benchEventSource) benchEventSource.close();
            benchEventSource = new EventSource(`/api/benchmark/stream`);

            benchEventSource.onmessage = function(event) {
                let parsed;
                try { parsed = JSON.parse(event.data); } catch { return; }

                switch (parsed.type) {
                    case 'model_start':
                        appendBenchLog(`[${parsed.index}/${parsed.total}] Testing model: ${parsed.model}...`);
                        break;

                    case 'model_done':
                        appendBenchLog(`[${parsed.index}/${parsed.total}] ${parsed.model} done.`, 'success');
                        if (parsed.result) appendBenchResult(parsed.result);
                        break;

                    case 'benchmark_done':
                        appendBenchLog('Benchmark completed!', 'success');
                        if (parsed.summary) {
                            appendBenchSummary(parsed.summary);
                        }
                        if (parsed.results) {
                            appendBenchAnalytics(parsed.results);
                        }
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        loadBenchHistory();
                        break;

                    case 'error':
                        appendBenchLog(`Error: ${parsed.message}`, 'error');
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        break;

                    case 'stream_end':
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        break;
                }
            };

            benchEventSource.onerror = function() {
                benchEventSource.close();
                benchEventSource = null;
                benchStartBtn.disabled = false;
            };

        } catch (err) {
            benchOutput.innerHTML = `<div class="bench-progress" style="color:var(--color-error);">Connection error: ${escapeHtml(err.message)}</div>`;
            benchStartBtn.disabled = false;
        }
    }

    function appendBenchLog(msg, type = 'info') {
        const placeholder = benchOutput.querySelector('.bench-placeholder');
        if (placeholder) placeholder.remove();
        const progress = benchOutput.querySelector('.bench-progress');
        if (progress) progress.remove();

        const line = document.createElement('div');
        line.className = `bench-log-line ${type}`;
        const ts = new Date().toLocaleTimeString();
        line.innerHTML = `<span style="opacity:0.5">[${ts}]</span> ${escapeHtml(msg)}`;
        benchOutput.appendChild(line);
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    function appendBenchResult(result) {
        const card = document.createElement('div');
        card.className = 'bench-result-card';

        const successCount = result.projects_results
            ? result.projects_results.filter(p => p.status === 'Success').length
            : 0;
        const totalTasks = result.projects_results ? result.projects_results.length : 0;
        const dur = result.duration_sec ? `${Math.floor(result.duration_sec / 60)}m ${Math.floor(result.duration_sec % 60)}s` : '-';

        card.innerHTML = `
            <div class="bench-result-header">
                <strong>${escapeHtml(result.model)}</strong>
                <span class="bench-result-size">${escapeHtml(result.model_size_human || '')}</span>
            </div>
            <div class="bench-result-stats">
                <div class="bench-stat">
                    <span class="bench-stat-value">${successCount}/${totalTasks}</span>
                    <span class="bench-stat-label">Tasks OK</span>
                </div>
                <div class="bench-stat">
                    <span class="bench-stat-value">${dur}</span>
                    <span class="bench-stat-label">Duration</span>
                </div>
                <div class="bench-stat">
                    <span class="bench-stat-value">${result.tokens_per_second || 0}</span>
                    <span class="bench-stat-label">tok/s</span>
                </div>
            </div>
        `;
        benchOutput.appendChild(card);
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    function appendBenchSummary(summary) {
        const summaryCard = document.createElement('div');
        summaryCard.className = 'bench-summary-card';
        summaryCard.innerHTML = `
            <div class="bench-summary-header">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style="margin-right: 8px; vertical-align: middle;">
                    <path d="M10 2L12.5 7H17.5L13.5 10.5L15 15.5L10 12.5L5 15.5L6.5 10.5L2.5 7H7.5L10 2Z" fill="var(--color-warning)"/>
                </svg>
                AI Intelligence Report
            </div>
            <div class="bench-summary-content">${formatAnswer ? formatAnswer(summary) : summary}</div>
        `;
        benchOutput.appendChild(summaryCard);
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    function appendBenchAnalytics(results) {
        if (!results || results.length === 0) return;

        const analyticsContainer = document.createElement('div');
        analyticsContainer.className = 'bench-analytics-container';
        
        let tableHtml = `
            <div class="bench-analytics-section">
                <h4>Performance Comparison</h4>
                <div class="bench-table-wrapper">
                    <table class="bench-table">
                        <thead>
                            <tr>
                                <th>Model</th>
                                <th>Success Rate</th>
                                <th>Avg Speed</th>
                                <th>Duration</th>
                                <th>Total Tokens</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        results.forEach(r => {
            const successTasks = r.projects_results ? r.projects_results.filter(p => p.status === 'Success').length : 0;
            const totalTasks = r.projects_results ? r.projects_results.length : 0;
            const successRate = totalTasks > 0 ? ((successTasks / totalTasks) * 100).toFixed(1) : 0;
            const duration = r.duration_sec ? `${(r.duration_sec / 60).toFixed(1)}m` : '-';
            
            tableHtml += `
                <tr>
                    <td><strong>${escapeHtml(r.model)}</strong></td>
                    <td class="${successRate > 70 ? 'text-success' : successRate > 40 ? 'text-warning' : 'text-error'}">${successRate}%</td>
                    <td>${r.tokens_per_second || 0} tok/s</td>
                    <td>${duration}</td>
                    <td>${r.total_tokens_session?.total || 0}</td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table></div></div>`;
        
        const chartId = 'bench-chart-' + Date.now();
        tableHtml += `
            <div class="bench-analytics-section">
                <h4>Speed vs Reliability (tok/s)</h4>
                <div class="bench-chart-wrapper">
                    <canvas id="${chartId}"></canvas>
                </div>
            </div>
        `;

        analyticsContainer.innerHTML = tableHtml;
        benchOutput.appendChild(analyticsContainer);
        benchOutput.scrollTop = benchOutput.scrollHeight;

        setTimeout(() => {
            const canvas = document.getElementById(chartId);
            if (!canvas || typeof Chart === 'undefined') return;
            const ctx = canvas.getContext('2d');
            const labels = results.map(r => r.model);
            const speeds = results.map(r => r.tokens_per_second || 0);
            const successRates = results.map(r => {
                const ok = r.projects_results ? r.projects_results.filter(p => p.status === 'Success').length : 0;
                return (ok / (r.projects_results?.length || 1)) * 100;
            });

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Speed (tok/s)',
                            data: speeds,
                            backgroundColor: 'rgba(99, 102, 241, 0.6)',
                            borderColor: 'rgba(99, 102, 241, 1)',
                            borderWidth: 1,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Success Rate (%)',
                            data: successRates,
                            type: 'line',
                            borderColor: '#10b981',
                            backgroundColor: '#10b981',
                            fill: false,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Tokens per Second', color: '#a1a1aa' },
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#a1a1aa' }
                        },
                        y1: {
                            beginAtZero: true,
                            max: 100,
                            position: 'right',
                            title: { display: true, text: 'Success Rate (%)', color: '#10b981' },
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#10b981' }
                        },
                        x: {
                            ticks: { color: '#a1a1aa' },
                            grid: { color: 'rgba(255, 255, 255, 0.05)' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#e4e4e7' } }
                    }
                }
            });
        }, 100);
    }

    async function loadBenchHistory() {
        if (!benchHistoryList) return;
        try {
            const resp = await fetch('/api/benchmark/results');
            const data = await resp.json();
            benchHistoryList.innerHTML = '';

            if (data.status === 'ok' && data.results.length > 0) {
                data.results.slice(0, 10).forEach(r => {
                    const item = document.createElement('button');
                    item.className = 'bench-history-item';
                    const date = new Date(r.modified * 1000).toLocaleString();
                    item.innerHTML = `<span>${escapeHtml(r.filename)}</span><span class="bench-history-date">${date}</span>`;
                    item.addEventListener('click', () => loadBenchResult(r.filename));
                    benchHistoryList.appendChild(item);
                });
            } else {
                benchHistoryList.innerHTML = '<div class="model-list-empty">No past results found</div>';
            }
        } catch (err) {
            if (benchHistoryList) benchHistoryList.innerHTML = '<div class="model-list-empty">Error loading results</div>';
        }
    }

    async function loadBenchResult(filename) {
        try {
            const resp = await fetch(`/api/benchmark/results/${encodeURIComponent(filename)}`);
            const data = await resp.json();
            if (data.status !== 'ok') return;

            benchOutput.innerHTML = '';
            appendBenchLog(`Loaded: ${filename}`);
            data.data.forEach(result => appendBenchResult(result));
        } catch (err) {
            console.error('Error loading bench result:', err);
        }
    }

    return {
        init: init,
        fetchModels: fetchModels,
        loadBenchHistory: loadBenchHistory
    };
})();
