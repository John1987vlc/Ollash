/**
 * Swarm Module for Ollash Agent
 * Visualizes multi-agent activity and coordination.
 */
window.SwarmModule = (function() {
    const specialists = ['code', 'network', 'system', 'cybersecurity', 'planner', 'prototyper'];
    let container;

    function init() {
        container = document.getElementById('swarm-nodes-container');
        if (container) {
            setupSwarmUI();
        }
        console.log("🚀 SwarmModule initialized");
    }

    function setupSwarmUI() {
        if (!container) return;
        container.innerHTML = '';
        specialists.forEach((spec, i) => {
            const angle = (i / specialists.length) * Math.PI * 2;
            const x = 200 + Math.cos(angle) * 150;
            const y = 200 + Math.sin(angle) * 150;
            
            const div = document.createElement('div');
            div.className = 'swarm-node';
            div.id = `swarm-node-${spec}`;
            div.style.left = `${x}px`;
            div.style.top = `${y}px`;
            div.textContent = spec.charAt(0).toUpperCase() + spec.slice(1);
            container.appendChild(div);
        });
    }

    function highlightAgent(agentType) {
        const node = document.getElementById(`swarm-node-${agentType}`);
        if (node) {
            node.classList.add('active');
            setTimeout(() => node.classList.remove('active'), 2000);
        }
    }

    return {
        init: init,
        highlightAgent: highlightAgent
    };
})();

// Co-working tool button handlers (swarm.html page)
document.addEventListener('DOMContentLoaded', () => {
    const runDocToTask = document.getElementById('run-doc-to-task');
    const runLogAudit = document.getElementById('run-log-audit');
    const runSummary = document.getElementById('run-summary');

    if (runDocToTask) {
        runDocToTask.addEventListener('click', async () => {
            const docName = document.getElementById('doc-to-task-name').value;
            const resultsDiv = document.getElementById('doc-to-task-results');
            resultsDiv.innerText = 'Analyzing and generating tasks...';
            try {
                const response = await fetch('/api/swarm/doc-to-task', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ document_name: docName })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) { resultsDiv.innerText = 'Error: ' + e.message; }
        });
    }

    if (runLogAudit) {
        runLogAudit.addEventListener('click', async () => {
            const logType = document.getElementById('log-type-select').value;
            const resultsDiv = document.getElementById('log-audit-results');
            resultsDiv.innerText = 'Auditing logs for risks...';
            try {
                const response = await fetch('/api/swarm/log-audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ log_type: logType })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) { resultsDiv.innerText = 'Error: ' + e.message; }
        });
    }

    if (runSummary) {
        runSummary.addEventListener('click', async () => {
            const docName = document.getElementById('summary-doc-name').value;
            const resultsDiv = document.getElementById('summary-results');
            resultsDiv.innerText = 'Generating executive summary...';
            try {
                const response = await fetch('/api/swarm/summary', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ document_name: docName })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) { resultsDiv.innerText = 'Error: ' + e.message; }
        });
    }
});
