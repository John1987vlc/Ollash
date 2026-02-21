/**
 * Architecture Module for Ollash Agent
 * Visualizes the project structure using vis.js
 */
window.ArchitectureModule = (function() {
    let kgContainer, kgNodes, kgEdges, kgNetwork;

    function init() {
        kgContainer = document.getElementById('architecture-graph');
        console.log("🚀 ArchitectureModule initialized");
    }

    async function loadArchitecture() {
        if (!kgContainer) return;
        kgContainer.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-text-muted)">Generating architecture graph...</div>';

        try {
            const resp = await fetch('/api/knowledge-graph/data');
            const data = await resp.json();

            if (!data.nodes || data.nodes.length === 0) {
                kgContainer.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-text-muted)">No architecture data available for this project.</div>';
                return;
            }

            if (typeof vis === 'undefined') {
                console.error("vis.js library not loaded");
                kgContainer.innerHTML = '<div style="color:var(--color-error)">Visualization library (vis.js) missing.</div>';
                return;
            }

            kgContainer.innerHTML = '';
            kgNodes = new vis.DataSet(data.nodes);
            kgEdges = new vis.DataSet(data.edges);

            const options = {
                nodes: {
                    shape: 'dot',
                    size: 16,
                    font: { size: 12, color: '#e4e4e7' },
                    borderWidth: 2,
                    shadow: true
                },
                edges: {
                    width: 2,
                    shadow: true,
                    color: { color: '#6366f1', highlight: '#818cf8' }
                },
                physics: {
                    enabled: true,
                    stabilization: { iterations: 200 }
                }
            };

            kgNetwork = new vis.Network(kgContainer, { nodes: kgNodes, edges: kgEdges }, options);
        } catch (err) {
            console.error('Error loading architecture:', err);
            kgContainer.innerHTML = `<div style="color:var(--color-error)">Error loading data: ${err.message}</div>`;
        }
    }

    return {
        init: init,
        loadArchitecture: loadArchitecture
    };
})();
