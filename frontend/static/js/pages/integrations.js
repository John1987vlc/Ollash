/**
 * Integrations Module - Triggers and Webhooks
 */
window.IntegrationsModule = (function() {
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
                            <input type="checkbox" ${t.active ? 'checked' : ''} onchange="IntegrationsModule.toggleTrigger('${t.id}')">
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

    function init() {
        loadTriggers();
        
        const triggerForm = document.getElementById('trigger-form');
        if (triggerForm) {
            triggerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                // Mock save implementation
                if (window.showMessage) window.showMessage('Trigger saved successfully', 'success');
                closeTriggerModal();
                loadTriggers(); 
            });
        }
    }

    function openTriggerModal() {
        const modal = document.getElementById('trigger-modal');
        if (modal) modal.style.display = 'flex';
    }

    function closeTriggerModal() {
        const modal = document.getElementById('trigger-modal');
        if (modal) modal.style.display = 'none';
    }

    async function toggleTrigger(id) {
        console.log("Toggle trigger", id);
        // Implement backend call if needed
    }

    return { 
        init: init,
        loadTriggers: loadTriggers,
        openTriggerModal: openTriggerModal,
        closeTriggerModal: closeTriggerModal,
        toggleTrigger: toggleTrigger
    };
})();

// Global helpers for inline onclicks
window.openTriggerModal = IntegrationsModule.openTriggerModal;
window.closeTriggerModal = IntegrationsModule.closeTriggerModal;
