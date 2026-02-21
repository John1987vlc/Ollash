// Decisions Inspector logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadDecisions() {
        const resp = await fetch('/api/decisions');
        const data = await resp.json();
        const container = document.getElementById('kg-details-content'); // Reusing or adding new
        // The requirement says "Inspector de Decisiones (Chain of Thought Viewer)"
        // Let's add it to the chat-view as a panel
    }

    window.toggleReasoningPanel = () => {
        const panel = document.getElementById('reasoning-panel');
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        if (panel.style.display === 'block') refreshReasoning();
    };

    async function refreshReasoning() {
        const resp = await fetch('/api/decisions');
        const data = await resp.json();
        const list = document.getElementById('reasoning-list');
        list.innerHTML = '';
        
        data.decisions.forEach(d => {
            const item = document.createElement('div');
            item.className = 'reasoning-item';
            item.innerHTML = `
                <div class="reasoning-header">
                    <span class="type">${d.decision_type}</span>
                    <span class="time">${new Date(d.timestamp).toLocaleTimeString()}</span>
                </div>
                <div class="reasoning-body">
                    <p><strong>Choice:</strong> ${d.choice}</p>
                    <p><strong>Reasoning:</strong> ${d.reasoning}</p>
                </div>
            `;
            list.appendChild(item);
        });
    }
});
