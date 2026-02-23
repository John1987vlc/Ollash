// Git Operations UI Logic
if (typeof window.GitModule === 'undefined') {
    window.GitModule = {
        init: function() {
            this.statusContainer = document.getElementById('git-file-container');
            this.diffViewer = document.getElementById('diff-content');
            this.logContainer = document.getElementById('git-log');
            
            if (!this.statusContainer) {
                console.debug("GitModule: elements missing (expected if not in git view)");
                return;
            }

            this.loadStatus();
            this.loadLog();
            
            // Attach event listeners
            const refreshBtn = document.getElementById('refresh-git');
            if (refreshBtn) {
                refreshBtn.onclick = () => this.loadStatus();
            }
        },

        loadStatus: async function() {
            if (!this.statusContainer) return;
            try {
                const response = await fetch('/git/api/status');
                const data = await response.json();
                
                const branchEl = document.getElementById('branch-info');
                if (branchEl) branchEl.textContent = `Branch: ${data.branch}`;
                
                this.renderFileList(data.files || []);
            } catch (error) {
                console.error('Failed to load git status:', error);
                if (this.statusContainer) this.statusContainer.innerHTML = '<div class="error-msg">Failed to load status</div>';
            }
        },

        renderFileList: function(files) {
            if (!this.statusContainer) return;
            this.statusContainer.innerHTML = '';
            if (files.length === 0) {
                this.statusContainer.innerHTML = '<div class="empty-state">Working directory clean ✨</div>';
                return;
            }

            files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'git-file-item';
                
                let statusIcon = '📝';
                let statusClass = 'modified';
                
                if (file.status.includes('A') || file.status.includes('?')) {
                    statusIcon = '✨';
                    statusClass = 'added';
                } else if (file.status.includes('D')) {
                    statusIcon = '🗑️';
                    statusClass = 'deleted';
                }

                item.innerHTML = `
                    <span class="status-icon ${statusClass}">${statusIcon}</span>
                    <span class="file-path">${file.file}</span>
                `;
                
                item.onclick = () => this.loadDiff(file.file);
                this.statusContainer.appendChild(item);
            });
        },

        loadDiff: async function(filePath) {
            if (!this.diffViewer) return;
            this.diffViewer.innerHTML = '<div class="loading">Loading diff...</div>';
            try {
                const response = await fetch(`/git/api/diff?file=${encodeURIComponent(filePath)}`);
                const data = await response.json();
                
                if (window.hljs && data.diff) {
                    const highlighted = hljs.highlight(data.diff, { language: 'diff' }).value;
                    this.diffViewer.innerHTML = `<pre><code>${highlighted}</code></pre>`;
                } else {
                    this.diffViewer.textContent = data.diff || "No diff content.";
                }
            } catch (error) {
                this.diffViewer.textContent = 'Error loading diff';
            }
        },

        loadLog: async function() {
            if (!this.logContainer) return;
            try {
                const response = await fetch('/git/api/log');
                const data = await response.json();
                
                this.logContainer.innerHTML = (data.log || []).map(entry => `
                    <div class="git-log-entry">
                        <span class="commit-hash">${entry.split(' - ')[0]}</span>
                        <span class="commit-msg">${entry.split(' - ').slice(1).join(' - ')}</span>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Failed to load git log', error);
            }
        },

        commitChanges: async function() {
            const message = (document.getElementById('commit-msg') || document.getElementById('commit-message'))?.value;
            if (!message) return alert('Please enter a commit message');
            
            try {
                const response = await fetch('/git/api/commit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                
                const result = await response.json();
                if (result.status === 'success') {
                    if (window.ModalManager) window.ModalManager.close('commit-modal');
                    this.loadStatus();
                    this.loadLog();
                    if (window.showMessage) window.showMessage('Changes committed successfully', 'success');
                } else {
                    alert('Commit failed: ' + result.error);
                }
            } catch (error) {
                alert('Commit failed: ' + error.message);
            }
        }
    };

    // Wire up listeners
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('git-file-container')) {
            GitModule.init();
        }

        const performCommitBtn = document.getElementById('perform-commit-btn');
        if (performCommitBtn) {
            performCommitBtn.addEventListener('click', () => GitModule.commitChanges());
        }

        const autoGenMsg = document.getElementById('auto-gen-msg');
        if (autoGenMsg) {
            autoGenMsg.addEventListener('click', async (e) => {
                e.preventDefault();
                try {
                    const response = await fetch('/git/api/diff-summary');
                    const data = await response.json();
                    const msgEl = document.getElementById('commit-msg');
                    if (msgEl && data.message) msgEl.value = data.message;
                } catch (err) {
                    console.error('Failed to auto-generate commit message:', err);
                }
            });
        }
    });
}
