/**
 * Integrations Module - Triggers and Webhooks
 */
const IntegrationsModule = (function() {
    async function loadTriggers() {
        const container = document.getElementById('trigger-list');
        if (!container) return;

        try {
            const response = await fetch('/api/integrations/triggers');
            const data = await response.json();
            
            container.innerHTML = data.triggers.map(t => `
                <div class="ifttt-card">
                    <div style="display:flex; justify-content:space-between;">
                        <h4>${t.name}</h4>
                        <label class="switch small">
                            <input type="checkbox" ${t.active ? 'checked' : ''} onchange="toggleTrigger('${t.id}')">
                            <span class="slider round"></span>
                        </label>
                    </div>
                    <div class="logic-flow">
                        <div class="flow-step">
                            <span class="step-icon">⚡</span>
                            <span>IF <strong>${t.event}</strong></span>
                        </div>
                        <div class="flow-step">
                            <span class="step-icon">👉</span>
                            <span>THEN <strong>${t.action}</strong></span>
                        </div>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '<p class="placeholder">No triggers configured.</p>';
        }
    }

    window.openTriggerModal = () => document.getElementById('trigger-modal').style.display = 'flex';
    window.closeTriggerModal = () => document.getElementById('trigger-modal').style.display = 'none';

    document.getElementById('trigger-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        // Mock save implementation
        window.showMessage('Trigger saved successfully', 'success');
        closeTriggerModal();
        loadTriggers(); // Refresh list (mock)
    });

    return { init: loadTriggers };
})();

// Initialize when view is active
window.loadIntegrations = IntegrationsModule.init;
