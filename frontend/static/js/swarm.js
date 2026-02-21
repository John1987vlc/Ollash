// Swarm Activity logic
document.addEventListener('DOMContentLoaded', () => {
    const specialists = ['code', 'network', 'system', 'cybersecurity', 'planner', 'prototyper'];
    const container = document.getElementById('swarm-nodes-container');

    function initSwarm() {
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

    function updateSwarm(activeSpecialist) {
        document.querySelectorAll('.swarm-node').forEach(n => n.classList.remove('active'));
        if (activeSpecialist) {
            const node = document.getElementById(`swarm-node-${activeSpecialist}`);
            if (node) node.classList.add('active');
        }
    }

    // Listen for agent activity events via EventSource (if implemented) or poll
    // For now, we'll listen to a global event if app.js emits it
    window.addEventListener('agentStarted', (e) => {
        updateSwarm(e.detail.role);
    });

    window.addEventListener('agentFinished', () => {
        updateSwarm(null);
    });

    initSwarm();
});
