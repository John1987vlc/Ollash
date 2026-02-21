/**
 * Knowledge Graph Visualizer (F11)
 * Uses vis.js for force-directed graph rendering.
 * Enhanced with: file navigation, severity coloring, SSE updates, filtering.
 */

class KnowledgeGraphVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.network = null;
        this.nodesDataset = null;
        this.edgesDataset = null;
        this.eventSource = null;
        this.activeFilter = null;
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
                error: { color: { background: '#ff1744', border: '#d50000' } },
                warning: { color: { background: '#ff9100', border: '#e65100' } },
                success: { color: { background: '#00e676', border: '#00c853' } },
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

            const coloredNodes = (data.nodes || []).map(node => this._applySeverityColor(node));

            this.nodesDataset = new vis.DataSet(coloredNodes);
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

            this._startSSE();

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

            const coloredNodes = (data.nodes || []).map(node => this._applySeverityColor(node));

            this.nodesDataset.clear();
            this.edgesDataset.clear();
            this.nodesDataset.add(coloredNodes);
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
            let fileLink = '';
            if (node.file_path) {
                const lineInfo = node.line_number ? `:${node.line_number}` : '';
                fileLink = `
                    <button class="kg-file-link" onclick="window.knowledgeGraph._openInEditor('${node.file_path}', ${node.line_number || 0})">
                        View in Editor: ${node.file_path}${lineInfo}
                    </button>`;
            }

            const severityBadge = node.severity
                ? `<span class="kg-severity kg-severity-${node.severity}">${node.severity.toUpperCase()}</span>`
                : '';

            detailsPanel.innerHTML = `
                <h4>${node.label}</h4>
                <span class="kg-badge">${node.group}</span>
                ${severityBadge}
                ${fileLink}
                <pre>${node.title || 'No metadata'}</pre>
            `;
            detailsPanel.style.display = 'block';
        }
    }

    filterByType(type) {
        if (!this.nodesDataset) return;

        if (this.activeFilter === type) {
            this.activeFilter = null;
            this.nodesDataset.forEach(node => {
                this.nodesDataset.update({ id: node.id, hidden: false });
            });
        } else {
            this.activeFilter = type;
            this.nodesDataset.forEach(node => {
                this.nodesDataset.update({
                    id: node.id,
                    hidden: node.group !== type,
                });
            });
        }
    }

    focusOnErrors() {
        this.filterByType('error');
    }

    showAll() {
        this.activeFilter = null;
        if (this.nodesDataset) {
            this.nodesDataset.forEach(node => {
                this.nodesDataset.update({ id: node.id, hidden: false });
            });
        }
    }

    _startSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        try {
            this.eventSource = new EventSource('/api/knowledge-graph/stream');

            this.eventSource.addEventListener('node_added', (event) => {
                const node = JSON.parse(event.data);
                if (this.nodesDataset && !this.nodesDataset.get(node.id)) {
                    this.nodesDataset.add(this._applySeverityColor(node));
                }
            });

            this.eventSource.addEventListener('edge_added', (event) => {
                const edge = JSON.parse(event.data);
                if (this.edgesDataset) {
                    this.edgesDataset.add(edge);
                }
            });

            this.eventSource.addEventListener('node_updated', (event) => {
                const node = JSON.parse(event.data);
                if (this.nodesDataset) {
                    this.nodesDataset.update(this._applySeverityColor(node));
                }
            });

            this.eventSource.onerror = () => {
                setTimeout(() => this._startSSE(), 5000);
            };
        } catch (err) {
            console.debug('Knowledge graph SSE not available:', err);
        }
    }

    _applySeverityColor(node) {
        if (node.severity) {
            const colorMap = {
                critical: { background: '#ff1744', border: '#d50000' },
                high: { background: '#ff5722', border: '#dd2c00' },
                medium: { background: '#ff9100', border: '#e65100' },
                low: { background: '#ffd740', border: '#ffab00' },
                info: { background: '#448aff', border: '#2962ff' },
            };
            const colors = colorMap[node.severity];
            if (colors) {
                node.color = colors;
            }
        }
        return node;
    }

    _openInEditor(filePath, lineNumber) {
        window.dispatchEvent(new CustomEvent('open-file-in-editor', {
            detail: { path: filePath, line: lineNumber }
        }));
    }

    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.network) {
            this.network.destroy();
            this.network = null;
        }
    }
}

// Global instance
window.KnowledgeGraphVisualizer = KnowledgeGraphVisualizer;
