// Visual Builder for Automations
document.addEventListener('DOMContentLoaded', () => {
    const vbContainer = document.getElementById('visual-builder-container');
    const vbBtn = document.getElementById('visual-builder-btn');
    const vbCancelBtn = document.getElementById('vb-cancel-btn');
    const vbSaveBtn = document.getElementById('vb-save-btn');
    const automationGrid = document.getElementById('automations-grid');
    const automationsView = document.getElementById('automations-view');

    // Trigger & Action Selects
    const triggerSelect = document.getElementById('vb-trigger-select');
    const actionSelect = document.getElementById('vb-action-select');
    const configPanel = document.getElementById('vb-config-panel');

    if (!vbContainer || !vbBtn) return;

    // --- State ---
    let currentConfig = {
        trigger: null,
        action: null,
        details: {}
    };

    // --- Event Listeners ---
    vbBtn.addEventListener('click', () => {
        automationGrid.style.display = 'none';
        vbContainer.style.display = 'flex';
        resetBuilder();
    });

    vbCancelBtn.addEventListener('click', () => {
        vbContainer.style.display = 'none';
        automationGrid.style.display = 'grid';
    });

    triggerSelect.addEventListener('change', (e) => {
        currentConfig.trigger = e.target.value;
        updateConfigPanel();
    });

    actionSelect.addEventListener('change', (e) => {
        currentConfig.action = e.target.value;
        updateConfigPanel();
    });

    vbSaveBtn.addEventListener('click', saveAutomation);

    // --- Functions ---

    function resetBuilder() {
        triggerSelect.value = "";
        actionSelect.value = "";
        configPanel.innerHTML = "";
        configPanel.style.display = "none";
        currentConfig = { trigger: null, action: null, details: {} };
    }

    function updateConfigPanel() {
        configPanel.innerHTML = '';
        
        if (!currentConfig.trigger && !currentConfig.action) {
            configPanel.style.display = 'none';
            return;
        }

        configPanel.style.display = 'block';
        const form = document.createElement('div');
        form.className = 'config-form';

        // Trigger Specifics
        if (currentConfig.trigger === 'schedule') {
            form.innerHTML += `
                <div class="form-group">
                    <label>Cron Expression (e.g., '0 8 * * *')</label>
                    <input type="text" id="cfg-cron" class="form-control" placeholder="* * * * *">
                </div>
            `;
        } else if (currentConfig.trigger === 'test_failure') {
             form.innerHTML += `
                <div class="form-group">
                    <label>Threshold (Failures)</label>
                    <input type="number" id="cfg-threshold" class="form-control" value="1">
                </div>
            `;
        }

        // Action Specifics
        if (currentConfig.action === 'run_agent') {
            form.innerHTML += `
                <div class="form-group">
                    <label>Agent Role</label>
                    <select id="cfg-agent" class="form-control">
                        <option value="system">System</option>
                        <option value="network">Network</option>
                        <option value="cybersecurity">Security</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Prompt / Command</label>
                    <textarea id="cfg-prompt" class="form-control" rows="3"></textarea>
                </div>
            `;
        } else if (currentConfig.action === 'notify_webhook') {
            form.innerHTML += `
                <div class="form-group">
                    <label>Webhook URL</label>
                    <input type="url" id="cfg-webhook" class="form-control" placeholder="https://...">
                </div>
            `;
        }

        form.innerHTML += `<div class="form-group"><label>Automation Name</label><input type="text" id="cfg-name" class="form-control" placeholder="My Automation"></div>`;

        configPanel.appendChild(form);
    }

    async function saveAutomation() {
        const nameInput = document.getElementById('cfg-name');
        if (!nameInput || !nameInput.value) {
            alert("Please provide a name.");
            return;
        }

        // Collect Data
        const data = {
            name: nameInput.value,
            trigger: currentConfig.trigger,
            action: currentConfig.action,
            config: {}
        };

        // Helper to safely get value
        const getVal = (id) => {
            const el = document.getElementById(id);
            return el ? el.value : null;
        };

        data.config.cron = getVal('cfg-cron');
        data.config.agent = getVal('cfg-agent');
        data.config.prompt = getVal('cfg-prompt');
        data.config.webhook = getVal('cfg-webhook');
        data.config.threshold = getVal('cfg-threshold');

        // Map to legacy backend structure for compatibility if needed, 
        // or send as new structure if backend supports it. 
        // For now, we adapt to the existing POST /api/automations if it fits,
        // or assume we need to extend the backend. 
        // The current backend expects: name, agent, prompt, schedule (or cron).
        
        const payload = {
            name: data.name,
            agent: data.config.agent || 'system', // Default fallback
            prompt: data.config.prompt || `Triggered by ${data.trigger} -> ${data.action}`,
            schedule: data.trigger === 'schedule' ? 'custom' : 'event', // 'event' might need backend support
            cron: data.config.cron,
            // Extra metadata for the new features
            meta: {
                trigger_type: data.trigger,
                action_type: data.action,
                webhook: data.config.webhook
            }
        };

        try {
            const response = await fetch('/api/automations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                // Success
                vbContainer.style.display = 'none';
                automationGrid.style.display = 'grid';
                // Trigger refresh from main app
                if (window.loadAutomations) window.loadAutomations();
            } else {
                const err = await response.json();
                alert('Failed to save: ' + (err.error || 'Unknown error'));
            }
        } catch (e) {
            console.error(e);
            alert('Error saving automation');
        }
    }
});
