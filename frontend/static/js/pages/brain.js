/**
 * Brain View Module - Decisions and Knowledge Graph
 */

const BrainModule = (function() {
    let cy; // Cytoscape instance

    function init() {
        initGraph();
        loadDecisions();
        setupEventListeners();
    }

    function initGraph() {
        cy = cytoscape({
            container: document.getElementById('knowledge-graph-container'),
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': 'data(color)',
                        'label': 'data(label)',
                        'color': '#fff',
                        'font-size': '10px',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 40,
                        'height': 40
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#333',
                        'target-arrow-color': '#333',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier'
                    }
                }
            ],
            layout: { name: 'cose', animate: true }
        });
    }

    async function loadDecisions() {
        const historyContainer = document.getElementById('decision-history');
        try {
            const response = await fetch('/api/analysis/decisions');
            const data = await response.json();
            
            if (data.decisions && data.decisions.length > 0) {
                historyContainer.innerHTML = data.decisions.map(d => `
                    <div class="decision-item">
                        <div class="decision-tag">${d.category}</div>
                        <div style="font-weight: 600; margin-top: 2px;">${d.decision}</div>
                        <div class="decision-reason">Reason: ${d.reason}</div>
                        <div style="font-size: 0.7rem; color: var(--color-text-subtle); margin-top: 5px;">
                            ${new Date(d.timestamp).toLocaleString()}
                        </div>
                    </div>
                `).join('');
            }
        } catch (error) {
            console.error('Error loading decisions:', error);
        }
    }

    async function refreshGraph() {
        try {
            const response = await fetch('/api/analysis/knowledge-graph');
            const data = await response.json();
            
            cy.elements().remove();
            cy.add(data.elements);
            cy.layout({ name: 'cose' }).run();
        } catch (error) {
            console.error('Error refreshing graph:', error);
        }
    }

    function setupEventListeners() {
        document.getElementById('refresh-graph').onclick = refreshGraph;
        document.getElementById('fit-graph').onclick = () => cy.fit();
        
        document.getElementById('toggle-decision-recording').onchange = async (e) => {
            const enabled = e.target.checked;
            await fetch('/api/settings/feature', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feature: 'decision_memory.auto_record', value: enabled })
            });
        };
    }

    return { init, refreshGraph };
})();

// Initialize when view is active
window.loadBrainData = BrainModule.init;
