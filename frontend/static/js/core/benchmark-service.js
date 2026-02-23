/**
 * Benchmark Service
 * Manages benchmark execution and global status tracking across the SPA.
 */
window.BenchmarkService = (function() {
    let eventSource = null;
    let isRunning = false;
    let activeModels = [];
    let currentTask = null;
    let completedModels = [];
    let listeners = [];

    function addListener(callback) {
        listeners.push(callback);
    }

    function removeListener(callback) {
        listeners = listeners.filter(l => l !== callback);
    }

    function notify(event) {
        listeners.forEach(l => l(event));
        
        // Global Notifications
        if (event.type === 'model_done') {
            window.showMessage(`Benchmark: Model ${event.model} completed!`, 'success');
        } else if (event.type === 'benchmark_done') {
            window.showMessage('Full Benchmark Suite completed!', 'success');
            isRunning = false;
        } else if (event.type === 'error') {
            window.showMessage(`Benchmark Error: ${event.message}`, 'error');
            isRunning = false;
        }
    }

    async function start(models, ollamaUrl) {
        if (isRunning) return { ok: false, message: 'Benchmark already running' };

        try {
            const resp = await fetch('/api/benchmark/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models, ollama_url: ollamaUrl })
            });
            const data = await resp.json();

            if (data.status !== 'started') {
                return { ok: false, message: data.message };
            }

            isRunning = true;
            activeModels = models;
            completedModels = [];
            
            connectStream();
            return { ok: true };
        } catch (err) {
            return { ok: false, message: err.message };
        }
    }

    function connectStream() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/benchmark/stream');

        eventSource.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            
            if (msg.type === 'task_start') {
                currentTask = msg;
            } else if (msg.type === 'model_done') {
                completedModels.push(msg.model);
            } else if (msg.type === 'benchmark_done' || msg.type === 'stream_end') {
                eventSource.close();
                isRunning = false;
            }

            notify(msg);
        };

        eventSource.onerror = () => {
            if (isRunning) {
                console.warn('Benchmark SSE connection lost. Attempting to reconnect...');
                setTimeout(connectStream, 2000);
            }
        };
    }

    return {
        start,
        addListener,
        removeListener,
        get isRunning() { return isRunning; },
        get currentTask() { return currentTask; },
        get completedModels() { return completedModels; }
    };
})();
