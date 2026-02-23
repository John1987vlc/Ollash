/**
 * Quick Benchmark Modal Logic
 * Uses global BenchmarkService for background tracking.
 */
window.BenchmarkModal = (function() {
    let modelList, startBtn, resultsContainer;

    function init() {
        modelList = document.getElementById('modal-bench-model-list');
        startBtn = document.getElementById('modal-bench-start-btn');
        resultsContainer = document.getElementById('modal-bench-results');

        if (startBtn) {
            startBtn.addEventListener('click', runBenchmark);
        }

        // Fetch models when modal opens
        document.querySelectorAll('[data-modal-open="benchmark-modal"]').forEach(btn => {
            btn.addEventListener('click', fetchModels);
        });

        // Listen to global events to update modal results if open
        if (window.BenchmarkService) {
            window.BenchmarkService.addListener(appendResult);
        }
    }

    function appendResult(msg) {
        if (!resultsContainer) return;

        if (msg.type === 'model_start') {
            const p = document.createElement('p');
            p.className = 'bench-modal-log-model';
            p.innerHTML = `<strong>> Model: ${msg.model}</strong>`;
            resultsContainer.appendChild(p);
        } else if (msg.type === 'task_start') {
            const p = document.createElement('p');
            p.className = 'bench-modal-log-task';
            p.style.marginLeft = '10px';
            p.style.fontSize = '0.8rem';
            p.textContent = `  - ${msg.task}...`;
            resultsContainer.appendChild(p);
        } else if (msg.type === 'model_done') {
            const div = document.createElement('div');
            div.className = 'bench-result-entry';
            div.innerHTML = `<strong>${msg.model}</strong>: ${msg.result.overall_status}`;
            resultsContainer.appendChild(div);
        } else if (msg.type === 'benchmark_done') {
            const div = document.createElement('div');
            div.className = 'success-msg';
            div.textContent = 'Benchmark complete!';
            resultsContainer.appendChild(div);
            if (startBtn) startBtn.disabled = false;
        }
        resultsContainer.scrollTop = resultsContainer.scrollHeight;
    }

    async function fetchModels() {
        if (!modelList) return;
        if (modelList.children.length > 1) return; // Already loaded

        modelList.innerHTML = '<div class="loading-spinner-small"></div>';
        
        try {
            const ollamaUrl = localStorage.getItem('ollash-ollama-url') || 'http://localhost:11434';
            const resp = await fetch(`/api/benchmark/models?url=${encodeURIComponent(ollamaUrl)}`);
            const data = await resp.json();

            if (data.status !== 'ok') {
                modelList.innerHTML = `<div class="error-msg">${data.message}</div>`;
                return;
            }

            modelList.innerHTML = '';
            data.models.forEach(m => {
                const label = document.createElement('label');
                label.className = 'model-checkbox-item';
                label.innerHTML = `
                    <input type="checkbox" value="${m.name}">
                    <span>${m.name}</span>
                `;
                modelList.appendChild(label);
            });
        } catch (err) {
            modelList.innerHTML = `<div class="error-msg">Error: ${err.message}</div>`;
        }
    }

    async function runBenchmark() {
        const checked = Array.from(modelList.querySelectorAll('input:checked')).map(cb => cb.value);
        if (checked.length === 0) {
            alert('Select at least one model.');
            return;
        }

        resultsContainer.innerHTML = '<p>Starting background run...</p>';
        if (startBtn) startBtn.disabled = true;

        const ollamaUrl = localStorage.getItem('ollash-ollama-url') || 'http://localhost:11434';
        const result = await window.BenchmarkService.start(checked, ollamaUrl);
        
        if (!result.ok) {
            resultsContainer.innerHTML = `<div class="error-msg">${result.message}</div>`;
            if (startBtn) startBtn.disabled = false;
        }
    }

    return { init };
})();
