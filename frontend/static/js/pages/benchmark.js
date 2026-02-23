/**
 * Ollash Model Benchmarking & Evaluation
 * Uses global BenchmarkService for persistent tracking.
 */

window.BenchmarkModule = (function() {
    let benchOllamaUrl, benchFetchModels, benchModelList, benchStartBtn, benchOutput, benchHistoryList;
    let evalPrompts, parallelEvalBtn, comparisonView, comparisonGrid, closeComparison;

    function init() {
        // Elements
        benchOllamaUrl = document.getElementById('bench-ollama-url');
        benchFetchModels = document.getElementById('bench-fetch-models');
        benchModelList = document.getElementById('bench-model-list');
        benchStartBtn = document.getElementById('bench-start-btn');
        benchOutput = document.getElementById('bench-output');
        benchHistoryList = document.getElementById('bench-history-list');
        
        evalPrompts = document.getElementById('eval-prompts');
        parallelEvalBtn = document.getElementById('parallel-eval-btn');
        comparisonView = document.getElementById('comparison-view');
        comparisonGrid = document.getElementById('comparison-grid');
        closeComparison = document.getElementById('close-comparison');

        if (!benchOutput) return;

        // --- Events ---
        if (benchFetchModels) benchFetchModels.onclick = fetchModels;
        if (benchStartBtn) benchStartBtn.onclick = startBenchmark;
        if (parallelEvalBtn) parallelEvalBtn.onclick = runParallelEval;
        
        if (closeComparison) {
            closeComparison.onclick = () => {
                comparisonView.style.display = 'none';
                benchOutput.style.display = 'block';
            };
        }

        // --- Listen to Global Benchmark Events ---
        if (window.BenchmarkService) {
            window.BenchmarkService.removeListener(appendLog); // Prevent duplicates
            window.BenchmarkService.addListener(appendLog);
        }

        // Initial state check
        if (window.BenchmarkService && window.BenchmarkService.isRunning) {
            benchStartBtn.disabled = true;
            benchOutput.innerHTML = '<p style="color:var(--color-primary)">🔄 A benchmark is running in background...</p>';
        }

        loadHistory();
        console.log("🚀 BenchmarkModule initialized");
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function appendLog(msg) {
        if (!benchOutput) return;
        
        if (msg.type === 'info' || msg.type === 'model_start') {
            const p = document.createElement('p');
            p.className = 'bench-log-entry';
            p.style.fontWeight = '600';
            p.style.color = 'var(--color-primary)';
            p.style.marginTop = '15px';
            p.innerHTML = `🤖 <strong>Testing Model: ${msg.model || msg.message}</strong>`;
            benchOutput.appendChild(p);
        } else if (msg.type === 'task_start') {
            const p = document.createElement('p');
            p.className = 'bench-log-entry task-entry';
            p.style.marginLeft = '20px';
            p.style.fontSize = '0.85rem';
            p.style.color = 'var(--color-text-muted)';
            const pct = Math.round((msg.task_index / msg.total_tasks) * 100);
            p.innerHTML = `📦 [${pct}%] Task ${msg.task_index}/${msg.total_tasks}: <span style="color:var(--color-text)">${msg.task}</span>...`;
            benchOutput.appendChild(p);
        } else if (msg.type === 'task_done') {
            const lastEntry = benchOutput.lastElementChild;
            if (lastEntry && lastEntry.classList.contains('task-entry')) {
                const isSuccess = msg.status === 'Success';
                const statusEmoji = isSuccess ? '✅' : '❌';
                const color = isSuccess ? '#10b981' : '#ef4444';
                lastEntry.innerHTML += ` <strong style="color:${color}">${statusEmoji} ${msg.status}</strong> <span style="font-size:0.7rem">(${msg.duration_sec.toFixed(1)}s)</span>`;
            }
        } else if (msg.type === 'model_done') {
            const div = document.createElement('div');
            div.className = 'stat-row';
            div.style.background = 'rgba(99, 102, 241, 0.05)';
            div.style.border = '1px solid var(--color-primary)';
            div.style.padding = '12px';
            div.style.borderRadius = '8px';
            div.style.margin = '15px 0';
            const status = msg.result.overall_status === 'Success' ? '✨ Success' : '⚠️ Partial Failure';
            div.innerHTML = `<h4>📊 Model ${msg.model} Results</h4>
                             <p>Status: <strong>${status}</strong> | Speed: <strong>${msg.result.tokens_per_second} t/s</strong></p>`;
            benchOutput.appendChild(div);
        } else if (msg.type === 'benchmark_done') {
            const div = document.createElement('div');
            div.className = 'success-msg';
            div.style.marginTop = '25px';
            div.style.padding = '20px';
            div.style.background = 'rgba(16, 185, 129, 0.1)';
            div.style.border = '1px solid #10b981';
            div.style.textAlign = 'center';
            div.innerHTML = `<h3>🏆 Benchmark Suite Complete!</h3><p>All models have been evaluated.</p>`;
            benchOutput.appendChild(div);
            loadHistory();
        }
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    // --- Standard Benchmark Logic ---
    async function fetchModels() {
        const url = benchOllamaUrl.value.trim();
        const params = url ? `?url=${encodeURIComponent(url)}` : '';
        const fetchBtn = document.getElementById('bench-fetch-models');
        const spinner = document.getElementById('fetch-spinner');
        const btnText = fetchBtn.querySelector('.btn-text');

        if (fetchBtn) fetchBtn.disabled = true;
        if (spinner) spinner.style.display = 'block';
        if (btnText) btnText.textContent = 'Fetching...';
        
        benchModelList.innerHTML = '<div class="loading-spinner-small"></div>';

        try {
            const resp = await fetch(`/api/benchmark/models${params}`);
            const data = await resp.json();

            if (data.status !== 'ok') {
                benchModelList.innerHTML = `<div class="error-msg">${escapeHtml(data.message)}</div>`;
                return;
            }

            if (!benchOllamaUrl.value.trim()) benchOllamaUrl.value = data.ollama_url;

            if (data.models.length === 0) {
                benchModelList.innerHTML = '<div class="empty-state">No models found</div>';
                return;
            }

            benchModelList.innerHTML = '';
            data.models.forEach(m => {
                if (m.supports_chat === false) return;
                
                const label = document.createElement('label');
                label.className = 'model-item';
                label.style.display = 'flex';
                label.style.alignItems = 'center';
                label.style.gap = '10px';
                label.style.padding = '8px';
                label.style.cursor = 'pointer';
                
                label.innerHTML = `
                    <input type="checkbox" value="${escapeHtml(m.name)}">
                    <span class="model-name">${escapeHtml(m.name)}</span>
                    <span class="model-size" style="font-size:0.7rem; color:var(--text-muted); margin-left:auto;">${escapeHtml(m.size_human)}</span>
                `;
                
                label.querySelector('input').onchange = () => {
                    const checked = benchModelList.querySelectorAll('input:checked').length;
                    benchStartBtn.disabled = checked === 0 || window.BenchmarkService.isRunning;
                };
                
                benchModelList.appendChild(label);
            });
        } catch (err) {
            benchModelList.innerHTML = `<div class="error-msg">Connection error: ${err.message}</div>`;
        } finally {
            if (fetchBtn) fetchBtn.disabled = false;
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.textContent = 'Fetch Available Models';
        }
    }

    async function startBenchmark() {
        const checked = Array.from(benchModelList.querySelectorAll('input:checked')).map(cb => cb.value);
        if (checked.length === 0) return;

        benchStartBtn.disabled = true;
        benchOutput.innerHTML = '<div class="loading-spinner"></div><p>Starting benchmark run...</p>';

        const result = await window.BenchmarkService.start(checked, benchOllamaUrl.value.trim());
        if (!result.ok) {
            benchOutput.innerHTML = `<div class="error-msg">${escapeHtml(result.message)}</div>`;
            benchStartBtn.disabled = false;
        }
    }

    // --- Parallel Evaluation Logic ---
    async function runParallelEval() {
        const checked = Array.from(benchModelList.querySelectorAll('input:checked')).map(cb => cb.value);
        if (checked.length === 0) {
            alert('Please select at least one model.');
            return;
        }

        const prompts = evalPrompts.value.trim().split('\n').filter(p => p);
        if (prompts.length === 0) {
            alert('Please enter at least one prompt.');
            return;
        }

        parallelEvalBtn.disabled = true;
        benchOutput.style.display = 'none';
        comparisonView.style.display = 'block';
        comparisonGrid.innerHTML = '<div class="loading-spinner"></div><p>Evaluating models in parallel...</p>';

        try {
            const response = await fetch('/api/benchmark/parallel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    models: checked,
                    prompts: prompts
                })
            });
            const data = await response.json();

            if (data.error) {
                comparisonGrid.innerHTML = `<div class="error-msg">Error: ${data.error}</div>`;
                parallelEvalBtn.disabled = false;
                return;
            }

            renderComparison(data.results, checked);
            loadShadowReport();

        } catch (err) {
            comparisonGrid.innerHTML = `<div class="error-msg">Failed to connect to evaluator: ${err.message}</div>`;
            parallelEvalBtn.disabled = false;
        }
    }

    function renderComparison(results, models) {
        comparisonGrid.innerHTML = '';
        
        models.forEach(model => {
            const card = document.createElement('div');
            card.className = 'comparison-card';
            
            // Collect results for this model
            let modelHtml = `<h4>${model}</h4>`;
            
            Object.keys(results).forEach(key => {
                if (key.startsWith(model)) {
                    const res = results[key];
                    modelHtml += `
                        <div class="comparison-content">
                            ${res.success ? escapeHtml(res.content) : `<span class="error-msg">${res.error}</span>`}
                        </div>
                        <hr style="opacity:0.1; margin: 15px 0;">
                    `;
                }
            });
            
            card.innerHTML = modelHtml + `<div class="shadow-stats" id="shadow-${model.replace(/[:.]/g, '-')}">Loading shadow metrics...</div>`;
            comparisonGrid.appendChild(card);
        });
        
        parallelEvalBtn.disabled = false;
    }

    async function loadShadowReport() {
        try {
            const response = await fetch('/api/benchmark/shadow-report');
            const data = await response.json();
            
            Object.keys(data.models).forEach(modelName => {
                const stats = data.models[modelName];
                const elementId = `shadow-${modelName.replace(/[:.]/g, '-')}`;
                const el = document.getElementById(elementId);
                
                if (el) {
                    el.innerHTML = `
                        <span class="shadow-tag">Correction Rate: ${(stats.correction_rate * 100).toFixed(0)}%</span>
                        <span class="shadow-tag">Severity: ${stats.avg_severity.toFixed(2)}</span>
                        ${stats.flagged ? '<span class="shadow-tag" style="background:rgba(239,68,68,0.1); color:#ef4444;">Flagged</span>' : ''}
                    `;
                }
            });
        } catch (err) {
            console.error('Error loading shadow report:', err);
        }
    }

    async function loadHistory() {
        try {
            const resp = await fetch('/api/benchmark/results');
            const data = await resp.json();
            if (!benchHistoryList) return;
            benchHistoryList.innerHTML = '';
            data.results.forEach(r => {
                const btn = document.createElement('button');
                btn.className = 'nav-item';
                btn.style.width = '100%';
                btn.style.textAlign = 'left';
                btn.style.marginBottom = '5px';
                btn.textContent = r.filename;
                benchHistoryList.appendChild(btn);
            });
        } catch (err) {}
    }

    return {
        init: init,
        loadHistory: loadHistory
    };
})();

// Re-init when script loads (initial load)
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('benchmark-view')) {
        BenchmarkModule.init();
    }
});
