/**
 * Quick Benchmark Modal Logic
 */
window.BenchmarkModal = (function() {
    let modelList, startBtn, resultsContainer;
    let eventSource = null;

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
    }

    async function fetchModels() {
        if (!modelList) return;
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

        resultsContainer.innerHTML = '<div class="loading-spinner"></div><p>Running benchmark...</p>';
        startBtn.disabled = true;

        try {
            const ollamaUrl = localStorage.getItem('ollash-ollama-url') || 'http://localhost:11434';
            const resp = await fetch('/api/benchmark/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models: checked, ollama_url: ollamaUrl })
            });
            
            if (eventSource) eventSource.close();
            eventSource = new EventSource('/api/benchmark/stream');

            eventSource.onmessage = (e) => {
                const msg = JSON.parse(e.data);
                if (msg.type === 'model_done') {
                    const div = document.createElement('div');
                    div.className = 'bench-result-entry';
                    div.innerHTML = `<strong>${msg.model}</strong>: ${(msg.result.success_rate * 100).toFixed(0)}% success`;
                    resultsContainer.appendChild(div);
                } else if (msg.type === 'benchmark_done') {
                    eventSource.close();
                    startBtn.disabled = false;
                }
            };
        } catch (err) {
            resultsContainer.innerHTML = `<div class="error-msg">Error: ${err.message}</div>`;
            startBtn.disabled = false;
        }
    }

    return { init };
})();
