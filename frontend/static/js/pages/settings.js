/**
 * Settings Page - Model Health & Routing loader
 * Previously inline script extracted to comply with CSP best practices.
 */
(function() {
    async function loadHealth() {
        const container = document.getElementById('model-health-container');
        if (!container) return;

        try {
            const res = await fetch('/api/health/');
            const data = await res.json();

            container.innerHTML = '';

            (data.models || []).forEach(model => {
                const card = document.createElement('div');
                card.className = 'metric-card';
                card.style.textAlign = 'left';
                card.style.padding = '15px';

                const statusColor = model.status === 'online' ? 'var(--color-success)' : 'var(--color-error)';
                const latencyColor = model.latency < 100 ? 'var(--color-success)' : 'var(--color-warning)';

                // Escape values before injecting into DOM
                const safeName = String(model.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const safeLatency = Number.isFinite(model.latency) ? model.latency : '—';
                const safeFallback = String(model.fallback || 'None').replace(/</g, '&lt;').replace(/>/g, '&gt;');

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
                            <option>${safeFallback}</option>
                            <option>llama3:8b</option>
                            <option>mistral:7b</option>
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

    document.addEventListener('DOMContentLoaded', loadHealth);
})();
