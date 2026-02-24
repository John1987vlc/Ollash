/**
 * StreamPanel — P4 Live Token Streaming Panels
 *
 * Creates per-file panels that display streamed code as it arrives from the LLM.
 * Responds to SSE events: blackboard_stream_chunk, file_generated.
 *
 * API:
 *   StreamPanel.init(containerSelector)
 *   StreamPanel.onChunk(relPath, chunk, agentId)
 *   StreamPanel.finalize(relPath)
 */
(function (global) {
    'use strict';

    let _container = null;
    const _panels  = {};   // relPath → { el, codeEl }

    const AGENT_COLORS = {
        developer_0: '#3b82f6',
        developer_1: '#22c55e',
        developer_2: '#a855f7',
        developer_3: '#f59e0b',
        developer_4: '#ec4899',
    };

    function init(containerSelector) {
        _container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;
    }

    function _ensurePanel(relPath, agentId) {
        if (_panels[relPath]) return _panels[relPath];

        const color = AGENT_COLORS[agentId] || '#6b7280';
        const panel = document.createElement('div');
        panel.className = 'stream-panel';
        panel.dataset.relPath = relPath;
        panel.style.setProperty('--agent-color', color);
        panel.innerHTML = `
            <div class="stream-panel-header">
                <span class="stream-panel-dot"></span>
                <span class="stream-panel-agent">${agentId || 'agent'}</span>
                <span class="stream-panel-path">${_esc(relPath)}</span>
                <span class="stream-panel-status">streaming…</span>
            </div>
            <div class="stream-panel-body">
                <pre class="stream-panel-code"><code id="sp-${_sid(relPath)}"></code><span class="stream-cursor">|</span></pre>
            </div>`;

        if (_container) _container.appendChild(panel);
        const codeEl = panel.querySelector(`#sp-${_sid(relPath)}`);
        _panels[relPath] = { el: panel, codeEl };
        return _panels[relPath];
    }

    function onChunk(relPath, chunk, agentId) {
        const p = _ensurePanel(relPath, agentId || 'agent');
        if (p.codeEl) {
            p.codeEl.textContent += chunk;
            const body = p.el.querySelector('.stream-panel-body');
            if (body) body.scrollTop = body.scrollHeight;
        }
    }

    function finalize(relPath) {
        const p = _panels[relPath];
        if (!p) return;
        const status = p.el.querySelector('.stream-panel-status');
        const cursor = p.el.querySelector('.stream-cursor');
        if (status) { status.textContent = 'done'; status.style.color = '#22c55e'; }
        if (cursor) cursor.style.display = 'none';

        setTimeout(() => {
            p.el.classList.add('stream-panel-dismissed');
            setTimeout(() => { p.el.remove(); delete _panels[relPath]; }, 400);
        }, 6000);
    }

    function _esc(s) { return String(s).replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function _sid(s) { return s.replace(/[^a-zA-Z0-9_-]/g, '_'); }

    global.StreamPanel = { init, onChunk, finalize };
})(window);
