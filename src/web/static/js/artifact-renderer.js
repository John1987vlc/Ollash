/**
 * Artifact Renderer for Knowledge Workspace
 * Renders Markdown, code, and document artifacts with enhanced styling
 */

class ArtifactRenderer {
    constructor() {
        this.artifacts = new Map();
        this.currentArtifactId = null;
        this.loadMarkedLibrary();
    }

    loadMarkedLibrary() {
        // Load marked.js for Markdown rendering
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/marked/latest/marked.umd.js';
        script.onload = () => {
            console.log('✓ Marked.js loaded for Markdown rendering');
        };
        document.head.appendChild(script);
    }

    /**
     * Register an artifact (document, markdown, code)
     */
    registerArtifact(id, content, type = 'markdown', metadata = {}) {
        const artifact = {
            id,
            content,
            type, // 'markdown', 'code', 'html', 'json', 'plan'
            metadata,
            created: new Date(),
            rendered: null,
            refactorHistory: []
        };
        this.artifacts.set(id, artifact);
        return artifact;
    }

    /**
     * Render an artifact to HTML
     */
    renderArtifact(id, container) {
        const artifact = this.artifacts.get(id);
        if (!artifact) {
            console.error(`Artifact not found: ${id}`);
            return;
        }

        this.currentArtifactId = id;
        let html = '';

        // Add artifact header
        html += this._renderHeader(artifact);

        // Render based on type
        switch (artifact.type) {
            case 'markdown':
                html += this._renderMarkdown(artifact);
                break;
            case 'code':
                html += this._renderCode(artifact);
                break;
            case 'html':
                html += this._renderHTML(artifact);
                break;
            case 'json':
                html += this._renderJSON(artifact);
                break;
            case 'plan':
                html += this._renderPlan(artifact);
                break;
            default:
                html += this._renderPlainText(artifact);
        }

        // Add action buttons
        html += this._renderActionButtons(artifact);

        container.innerHTML = html;
        artifact.rendered = html;

        // Highlight code blocks if needed
        this._highlightCodeBlocks(container);
    }

    _renderHeader(artifact) {
        const typeEmoji = {
            'markdown': '📄',
            'code': '💻',
            'html': '🌐',
            'json': '📊',
            'plan': '📋'
        };

        return `
            <div class="artifact-header">
                <div class="artifact-header-left">
                    <span class="artifact-type-emoji">${typeEmoji[artifact.type] || '📑'}</span>
                    <div class="artifact-info">
                        <h3 class="artifact-title">${artifact.metadata.title || artifact.id}</h3>
                        <p class="artifact-meta">
                            Type: <strong>${artifact.type}</strong> • 
                            Created: ${artifact.created.toLocaleString()}
                            ${artifact.metadata.source ? ` • Source: ${artifact.metadata.source}` : ''}
                        </p>
                    </div>
                </div>
                <div class="artifact-header-stats">
                    ${artifact.metadata.wordCount ? `<span class="stat">${artifact.metadata.wordCount} words</span>` : ''}
                    ${artifact.metadata.compression ? `<span class="stat">Compression: ${artifact.metadata.compression}</span>` : ''}
                </div>
            </div>
        `;
    }

    _renderMarkdown(artifact) {
        try {
            // Use marked.js if available, fallback to basic rendering
            const html = window.marked ? window.marked.parse(artifact.content) : this._basicMarkdownToHTML(artifact.content);
            return `
                <div class="artifact-content markdown-content">
                    ${html}
                </div>
            `;
        } catch (e) {
            console.error('Markdown rendering error:', e);
            return this._renderPlainText(artifact);
        }
    }

    _renderCode(artifact) {
        const language = artifact.metadata.language || 'plaintext';
        return `
            <div class="artifact-content code-content">
                <div class="code-lang-label">${language}</div>
                <pre><code class="language-${language}">${this._escapeHTML(artifact.content)}</code></pre>
            </div>
        `;
    }

    _renderHTML(artifact) {
        return `
            <div class="artifact-content html-content">
                <iframe class="html-preview" sandbox="allow-scripts allow-same-origin allow-popups"></iframe>
            </div>
        `;
    }

    _renderJSON(artifact) {
        let jsonObj;
        try {
            jsonObj = typeof artifact.content === 'string' 
                ? JSON.parse(artifact.content) 
                : artifact.content;
        } catch (e) {
            return this._renderPlainText(artifact);
        }

        const prettyJSON = JSON.stringify(jsonObj, null, 2);
        return `
            <div class="artifact-content json-content">
                <pre><code class="language-json">${this._escapeHTML(prettyJSON)}</code></pre>
            </div>
        `;
    }

    _renderPlan(artifact) {
        // Special rendering for task/automation plans
        return `
            <div class="artifact-content plan-content">
                <div class="plan-container">
                    ${this._parsePlanContent(artifact.content)}
                </div>
            </div>
        `;
    }

    _renderPlainText(artifact) {
        return `
            <div class="artifact-content text-content">
                <pre>${this._escapeHTML(artifact.content)}</pre>
            </div>
        `;
    }

    _renderActionButtons(artifact) {
        return `
            <div class="artifact-actions">
                <button class="btn-artifact" onclick="artifactRenderer.refactorArtifact('${artifact.id}', 'shorten')">
                    <span>✂️</span> Acortar
                </button>
                <button class="btn-artifact" onclick="artifactRenderer.refactorArtifact('${artifact.id}', 'formal')">
                    <span>🎩</span> Tono Profesional
                </button>
                <button class="btn-artifact" onclick="artifactRenderer.refactorArtifact('${artifact.id}', 'expand')">
                    <span>📖</span> Expandir
                </button>
                <button class="btn-artifact" onclick="artifactRenderer.copyToClipboard('${artifact.id}')">
                    <span>📋</span> Copiar
                </button>
                <button class="btn-artifact" onclick="artifactRenderer.downloadArtifact('${artifact.id}')">
                    <span>⬇️</span> Descargar
                </button>
            </div>
        `;
    }

    /**
     * Request refactoring of an artifact
     */
    refactorArtifact(id, refactorType) {
        const artifact = this.artifacts.get(id);
        if (!artifact) return;

        // Send refactoring request to agent
        const message = {
            type: 'refactor_artifact',
            artifact_id: id,
            current_content: artifact.content,
            refactor_type: refactorType,
            metadata: artifact.metadata
        };

        // Post to chat/agent endpoint
        fetch('/api/chat/refactor-artifact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message)
        })
        .then(r => r.json())
        .then(data => {
            if (data.refactored_content) {
                artifact.content = data.refactored_content;
                artifact.refactorHistory.push({
                    type: refactorType,
                    timestamp: new Date(),
                    result: data
                });
                // Re-render
                const container = document.querySelector('.artifact-container');
                if (container) this.renderArtifact(id, container);
            }
        })
        .catch(e => console.error('Refactoring failed:', e));
    }

    /**
     * Copy artifact content to clipboard
     */
    copyToClipboard(id) {
        const artifact = this.artifacts.get(id);
        if (!artifact) return;

        navigator.clipboard.writeText(artifact.content).then(() => {
            // Show toast notification
            this._showToast('✓ Copiado al portapapeles', 'success');
        });
    }

    /**
     * Download artifact as file
     */
    downloadArtifact(id) {
        const artifact = this.artifacts.get(id);
        if (!artifact) return;

        const extensions = {
            'markdown': 'md',
            'code': artifact.metadata.language || 'txt',
            'html': 'html',
            'json': 'json',
            'plan': 'txt'
        };

        const ext = extensions[artifact.type] || 'txt';
        const filename = `${artifact.metadata.title || artifact.id}.${ext}`;

        const element = document.createElement('a');
        element.setAttribute('href', `data:text/plain;charset=utf-8,${encodeURIComponent(artifact.content)}`);
        element.setAttribute('download', filename);
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);

        this._showToast(`✓ Descargado: ${filename}`, 'success');
    }

    // ===== PRIVATE HELPERS =====

    _basicMarkdownToHTML(md) {
        // Simple fallback markdown processing if marked.js not loaded
        let html = this._escapeHTML(md);
        
        // Headers
        html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
        
        // Bold and italic
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Code blocks
        html = html.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');
        
        // Line breaks
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }

    _parsePlanContent(content) {
        // Parse task/plan JSON into visual format
        try {
            const plan = typeof content === 'string' ? JSON.parse(content) : content;
            
            if (Array.isArray(plan)) {
                return plan.map((task, i) => `
                    <div class="plan-task">
                        <div class="task-header">
                            <span class="task-number">${i + 1}</span>
                            <h4>${task.name || task.title}</h4>
                            <span class="task-priority ${task.priority}">${task.priority || 'medium'}</span>
                        </div>
                        <p>${task.description || ''}</p>
                        ${task.acceptance_criteria ? `
                            <div class="task-criteria">
                                <strong>Aceptación:</strong>
                                ${Array.isArray(task.acceptance_criteria) 
                                    ? '<ul>' + task.acceptance_criteria.map(c => `<li>${c}</li>`).join('') + '</ul>'
                                    : `<p>${task.acceptance_criteria}</p>`}
                            </div>
                        ` : ''}
                        ${task.estimated_effort ? `<span class="task-effort">⏱️ ${task.estimated_effort} horas</span>` : ''}
                    </div>
                `).join('');
            }
        } catch (e) {
            return this._escapeHTML(content);
        }
    }

    _highlightCodeBlocks(container) {
        // Use Highlight.js if available
        if (window.hljs) {
            container.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        }
    }

    _escapeHTML(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    _showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }
}

// Global instance
const artifactRenderer = new ArtifactRenderer();

