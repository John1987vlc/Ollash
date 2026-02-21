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
