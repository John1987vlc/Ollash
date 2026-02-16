/**
 * Knowledge Graph Visualizer (F11)
 * Uses vis.js for force-directed graph rendering.
 */

class KnowledgeGraphVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.network = null;
        this.nodesDataset = null;
        this.edgesDataset = null;
        this.options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: { size: 12, color: '#e0e0e0' },
                borderWidth: 2,
            },
            edges: {
                arrows: 'to',
                color: { color: '#555', highlight: '#8ab4f8' },
                font: { size: 10, color: '#888', align: 'middle' },
                smooth: { type: 'cubicBezier' },
            },
            groups: {
                term: { color: { background: '#4285f4', border: '#2a56c6' } },
                document: { color: { background: '#34a853', border: '#1e7e34' } },
                section: { color: { background: '#fbbc04', border: '#c79400' } },
                concept: { color: { background: '#ea4335', border: '#b31412' } },
            },
            physics: {
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 100,
                    springConstant: 0.08,
                },
                stabilization: { iterations: 150 },
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                navigationButtons: true,
                keyboard: true,
            },
        };
    }

    async loadGraph() {
        try {
            const resp = await fetch('/api/knowledge-graph/data');
            const data = await resp.json();

            this.nodesDataset = new vis.DataSet(data.nodes || []);
            this.edgesDataset = new vis.DataSet(data.edges || []);

            if (this.network) {
                this.network.destroy();
            }

            this.network = new vis.Network(
                this.container,
                { nodes: this.nodesDataset, edges: this.edgesDataset },
                this.options
            );

            this.network.on('click', (params) => {
                if (params.nodes.length > 0) {
                    this.showNodeDetails(params.nodes[0]);
                }
            });

            this.network.on('doubleClick', (params) => {
                if (params.nodes.length > 0) {
                    this.loadNeighborhood(params.nodes[0]);
                }
            });

            return data;
        } catch (err) {
            console.error('Failed to load knowledge graph:', err);
            if (this.container) {
                this.container.innerHTML =
                    '<p style="color:#888;text-align:center;padding:2em;">No knowledge graph data available.</p>';
            }
        }
    }

    async search(query) {
        try {
            const resp = await fetch(`/api/knowledge-graph/search?q=${encodeURIComponent(query)}`);
            const data = await resp.json();
            return data.results || [];
        } catch (err) {
            console.error('Graph search failed:', err);
            return [];
        }
    }

    async loadNeighborhood(nodeId, depth = 2) {
        try {
            const resp = await fetch(
                `/api/knowledge-graph/neighborhood/${encodeURIComponent(nodeId)}?depth=${depth}`
            );
            const data = await resp.json();

            this.nodesDataset.clear();
            this.edgesDataset.clear();
            this.nodesDataset.add(data.nodes || []);
            this.edgesDataset.add(data.edges || []);

            if (this.network) {
                this.network.fit();
            }
        } catch (err) {
            console.error('Neighborhood load failed:', err);
        }
    }

    showNodeDetails(nodeId) {
        const node = this.nodesDataset.get(nodeId);
        if (!node) return;

        const detailsPanel = document.getElementById('kg-node-details');
        if (detailsPanel) {
            detailsPanel.innerHTML = `
                <h4>${node.label}</h4>
                <span class="kg-badge">${node.group}</span>
                <pre>${node.title || 'No metadata'}</pre>
            `;
            detailsPanel.style.display = 'block';
        }
    }

    destroy() {
        if (this.network) {
            this.network.destroy();
            this.network = null;
        }
    }
}

// Global instance
window.KnowledgeGraphVisualizer = KnowledgeGraphVisualizer;
