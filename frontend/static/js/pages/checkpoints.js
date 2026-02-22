/**
 * Checkpoints Module - Time Travel for Projects
 */
const CheckpointsModule = (function() {
    async function loadCheckpoints() {
        const container = document.getElementById('timeline-list');
        if (!container) return;

        try {
            const response = await fetch('/api/checkpoints/list');
            const data = await response.json();
            
            container.innerHTML = data.checkpoints.map(cp => `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-meta">
                            <span>${new Date(cp.timestamp * 1000).toLocaleString()}</span>
                            <span class="tag ${cp.type}">${cp.type}</span>
                        </div>
                        <h4>${cp.message || 'System Checkpoint'}</h4>
                        <div style="font-size: 0.85rem; color: var(--color-text-muted); margin: 10px 0;">
                            Files changed: ${cp.files_count || 0}
                        </div>
                        <button class="btn-secondary btn-small" onclick="restoreCheckpoint('${cp.id}')">
                            Restore this version
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading checkpoints:', error);
            container.innerHTML = '<p class="error-msg">Failed to load timeline.</p>';
        }
    }

    window.createCheckpoint = async function() {
        const msg = prompt("Checkpoint Description:");
        if (!msg) return;
        
        try {
            await fetch('/api/checkpoints/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: msg, type: 'manual' })
            });
            loadCheckpoints();
            window.showMessage('Checkpoint created', 'success');
        } catch (e) {
            window.showMessage('Creation failed', 'error');
        }
    };

    window.restoreCheckpoint = async function(id) {
        if (!confirm('Are you sure? Current unsaved changes will be lost.')) return;
        
        try {
            await fetch(`/api/checkpoints/restore/${id}`, { method: 'POST' });
            window.showMessage('Project restored successfully', 'success');
            // Reload file tree if available
            if (window.ProjectsModule) window.ProjectsModule.refreshFileTree();
        } catch (e) {
            window.showMessage('Restore failed', 'error');
        }
    };

    return { init: loadCheckpoints };
})();

// Initialize when view is active
window.loadCheckpoints = CheckpointsModule.init;
