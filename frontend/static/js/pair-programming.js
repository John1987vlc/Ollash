/**
 * Pair Programming Mode (F12)
 * Real-time collaborative code editing via SSE.
 */

class PairProgrammingUI {
    constructor() {
        this.sessionId = null;
        this.eventSource = null;
        this.editor = null;
        this.isPaused = false;
        this.editsCount = 0;
    }

    async createSession() {
        try {
            const resp = await fetch('/api/pair-programming/sessions', { method: 'POST' });
            const data = await resp.json();
            this.sessionId = data.session_id;
            this._connectSSE();
            this._updateStatus('active');
            return data;
        } catch (err) {
            console.error('Failed to create pair programming session:', err);
        }
    }

    _connectSSE() {
        if (!this.sessionId) return;

        this.eventSource = new EventSource(
            `/api/pair-programming/sessions/${this.sessionId}/stream`
        );

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._handleEvent(data);
            } catch (e) {
                // keepalive or parse error
            }
        };

        this.eventSource.onerror = () => {
            console.warn('Pair programming SSE connection error');
        };
    }

    _handleEvent(data) {
        const type = data.type;

        if (type === 'pair_programming_file_start') {
            this._onFileStart(data.file_path);
        } else if (type === 'pair_programming_update') {
            this._onContentUpdate(data.content, data.cursor_position, data.source);
        } else if (type === 'pair_programming_file_complete') {
            this._onFileComplete(data.file_path, data.content);
        } else if (type === 'pair_programming_paused') {
            this._updateStatus('paused');
        } else if (type === 'pair_programming_resumed') {
            this._updateStatus('active');
        } else if (type === 'pair_programming_ended') {
            this._updateStatus('ended');
            this.disconnect();
        } else if (type === 'pair_programming_intervention') {
            this._onContentUpdate(data.content, -1, 'user');
        }
    }

    _onFileStart(filePath) {
        this.editsCount = 0;
        const fileLabel = document.getElementById('pp-current-file');
        if (fileLabel) fileLabel.textContent = filePath;

        const editorEl = document.getElementById('pp-editor');
        if (editorEl) editorEl.value = '';
    }

    _onContentUpdate(content, cursorPos, source) {
        this.editsCount++;
        const editorEl = document.getElementById('pp-editor');
        if (editorEl) {
            editorEl.value = content;
            if (cursorPos >= 0) {
                editorEl.setSelectionRange(cursorPos, cursorPos);
            }
        }

        const sourceLabel = document.getElementById('pp-last-source');
        if (sourceLabel) sourceLabel.textContent = source;

        const countLabel = document.getElementById('pp-edit-count');
        if (countLabel) countLabel.textContent = this.editsCount;
    }

    _onFileComplete(filePath, content) {
        const editorEl = document.getElementById('pp-editor');
        if (editorEl) editorEl.value = content;
        this._updateStatus('file_complete');
    }

    _updateStatus(status) {
        const statusEl = document.getElementById('pp-status');
        if (statusEl) {
            const labels = {
                active: 'Active',
                paused: 'Paused',
                ended: 'Session Ended',
                file_complete: 'File Complete',
            };
            statusEl.textContent = labels[status] || status;
            statusEl.className = `pp-status-badge pp-status-${status}`;
        }
    }

    async pause() {
        if (!this.sessionId) return;
        await fetch(`/api/pair-programming/sessions/${this.sessionId}/pause`, { method: 'POST' });
        this.isPaused = true;
    }

    async resume() {
        if (!this.sessionId) return;
        await fetch(`/api/pair-programming/sessions/${this.sessionId}/resume`, { method: 'POST' });
        this.isPaused = false;
    }

    async submitIntervention() {
        if (!this.sessionId) return;
        const editorEl = document.getElementById('pp-editor');
        if (!editorEl) return;

        await fetch(`/api/pair-programming/sessions/${this.sessionId}/intervene`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: editorEl.value,
                cursor_position: editorEl.selectionStart,
            }),
        });
    }

    async endSession() {
        if (!this.sessionId) return;
        await fetch(`/api/pair-programming/sessions/${this.sessionId}/end`, { method: 'POST' });
        this.disconnect();
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

window.PairProgrammingUI = PairProgrammingUI;
