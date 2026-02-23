/**
 * Settings Page - Model Health, Routing & Remote Ollama Config
 */
(function() {
    let availableModels = [];

    async function loadSettings() {
        const urlInput = document.getElementById('config-ollama-url');
        const agentNameInput = document.getElementById('config-agent-name');
        
        if (urlInput) {
            urlInput.value = localStorage.getItem('ollash-ollama-url') || 'http://localhost:11434';
            urlInput.addEventListener('change', (e) => {
                localStorage.setItem('ollash-ollama-url', e.target.value);
                loadHealth(); // Reload health and models when URL changes
            });
        }

        if (agentNameInput) {
            agentNameInput.value = localStorage.getItem('ollash-agent-name') || 'Ollash Default Agent';
            agentNameInput.addEventListener('change', (e) => {
                localStorage.setItem('ollash-agent-name', e.target.value);
            });
        }
    }

    async function fetchOllamaModels() {
        const ollamaUrl = localStorage.getItem('ollash-ollama-url') || 'http://localhost:11434';
        try {
            // We might need a backend proxy to avoid CORS if Ollama is remote
            // But let's try direct fetch first as Ollama usually allows local origins
            const res = await fetch(`${ollamaUrl}/api/tags`);
            if (res.ok) {
                const data = await res.json();
                availableModels = data.models.map(m => m.name);
                console.log('Fetched models from Ollama:', availableModels);
            }
        } catch (err) {
            console.warn('Could not fetch models directly from Ollama (CORS or Offline).', err);
            // Fallback to current system models if remote fetch fails
        }
    }

    async function loadHealth() {
        const container = document.getElementById('model-health-container');
        if (!container) return;

        await fetchOllamaModels();

        try {
            const res = await fetch('/api/health/');
            const data = await res.json();

            container.innerHTML = '';

            const modelsToDisplay = data.models || [];
            
            modelsToDisplay.forEach(model => {
                const card = document.createElement('div');
                card.className = 'metric-card';
                card.style.textAlign = 'left';
                card.style.padding = '15px';

                const statusColor = model.status === 'online' ? 'var(--color-success)' : 'var(--color-error)';
                const latencyColor = model.latency < 100 ? 'var(--color-success)' : 'var(--color-warning)';

                const safeName = String(model.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const safeLatency = Number.isFinite(model.latency) ? model.latency : '—';
                const safeFallback = String(model.fallback || 'None').replace(/</g, '&lt;').replace(/>/g, '&gt;');

                // Build options: dynamic models + current fallback if not in list
                let optionsHtml = `<option value="${model.fallback || ''}">${safeFallback}</option>`;
                
                const uniqueModels = new Set([...availableModels, 'gemma3:12b', 'ministral-3:8b', 'qwen3-coder:30b']);
                uniqueModels.forEach(mName => {
                    if (mName !== model.fallback) {
                        optionsHtml += `<option value="${mName}">${mName}</option>`;
                    }
                });

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <strong>${safeName}</strong>
                        <span style="width:8px; height:8px; border-radius:50%; background:${statusColor}; box-shadow:0 0 5px ${statusColor};"
                              role="img" aria-label="Estado: ${model.status === 'online' ? 'en línea' : 'desconectado'}"></span>
                    </div>
                    <div style="font-size:0.85rem; color:var(--color-text-muted);">
                        Latency: <span style="color:${latencyColor}">${safeLatency}ms</span>
                    </div>
                    <div style="margin-top:10px;">
                        <label style="font-size:0.7rem; text-transform:uppercase;">Fallback Model</label>
                        <select class="form-input" style="padding:4px; font-size:0.8rem;" aria-label="Fallback model para ${safeName}">
                            ${optionsHtml}
                        </select>
                    </div>
                `;
                container.appendChild(card);
            });
        } catch (err) {
            console.error('Error loading model health:', err);
            if (container) {
                container.innerHTML = '<p style="color:var(--color-error); padding: 1rem;">Error al cargar el estado de los modelos.</p>';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadSettings();
        loadHealth();
    });
})();
