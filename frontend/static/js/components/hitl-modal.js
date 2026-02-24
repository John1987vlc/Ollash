/**
 * HITL Modal + Task Inspector — P1 & P6
 *
 * Exports:
 *   HITLModal.show(taskId, agentId, question)   — open the HITL input modal
 *   HITLModal.hide()                             — close the modal
 *   TaskInspector.open(nodeData)                 — slide-in inspector panel
 *   TaskInspector.close()                        — close inspector
 */
(function (global) {
    'use strict';

    // -----------------------------------------------------------------------
    // HITL Modal
    // -----------------------------------------------------------------------

    const HITLModal = (() => {
        let _currentTaskId = null;

        const _q = id => document.getElementById(id);

        function show(taskId, agentId, question) {
            _currentTaskId = taskId;
            const overlay = _q('hitl-modal-overlay');
            if (!overlay) return;

            const q = _q('hitl-modal-question');
            const a = _q('hitl-modal-agent');
            const t = _q('hitl-task-id-display');
            const ta = _q('hitl-answer-input');

            if (q)  q.textContent  = question || 'Agent requires your input.';
            if (a)  a.textContent  = agentId  || 'agent';
            if (t)  t.textContent  = taskId   || '—';
            if (ta) ta.value = '';

            overlay.removeAttribute('hidden');
            if (ta) ta.focus();
        }

        function hide() {
            const overlay = _q('hitl-modal-overlay');
            if (overlay) overlay.setAttribute('hidden', '');
            _currentTaskId = null;
        }

        async function _submit(response) {
            const ta = _q('hitl-answer-input');
            const answer = (ta ? ta.value.trim() : '') || response;
            if (!_currentTaskId) { hide(); return; }

            try {
                await fetch('/api/hil/respond', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        request_id: _currentTaskId,
                        response,
                        feedback: answer,
                    }),
                });
            } catch (err) {
                console.warn('[HITLModal] respond failed:', err);
            }
            hide();
        }

        function _init() {
            document.addEventListener('click', e => {
                if (e.target.id === 'hitl-submit-btn') _submit('approve');
                if (e.target.id === 'hitl-reject-btn') _submit('reject');
                if (e.target.id === 'hitl-modal-overlay') hide();
            });
            document.addEventListener('keydown', e => {
                if (e.key === 'Escape') hide();
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    const ov = _q('hitl-modal-overlay');
                    if (ov && !ov.hidden) _submit('approve');
                }
            });
        }

        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _init);
        else _init();

        return { show, hide };
    })();

    // -----------------------------------------------------------------------
    // Task Inspector (slide-in panel from the right)
    // -----------------------------------------------------------------------

    const TaskInspector = (() => {
        let _panel = null;

        function _ensurePanel() {
            if (_panel) return _panel;
            _panel = document.createElement('aside');
            _panel.id = 'task-inspector';
            _panel.className = 'task-inspector';
            _panel.setAttribute('aria-label', 'Task Inspector');
            _panel.innerHTML = `
                <div class="task-inspector-header">
                    <span class="task-inspector-title" id="ti-title">Task Details</span>
                    <button class="task-inspector-close" id="ti-close" aria-label="Close">&times;</button>
                </div>
                <div class="task-inspector-tabs" role="tablist">
                    <button class="ti-tab active" data-tab="details" role="tab">Details</button>
                    <button class="ti-tab" data-tab="diff" role="tab">Diff</button>
                </div>
                <div class="task-inspector-body">
                    <div id="ti-tab-details" class="ti-tab-panel active"></div>
                    <div id="ti-tab-diff"    class="ti-tab-panel" hidden></div>
                </div>`;
            document.body.appendChild(_panel);

            _panel.querySelector('#ti-close').addEventListener('click', close);
            _panel.querySelectorAll('.ti-tab').forEach(btn =>
                btn.addEventListener('click', () => switchTab(btn.dataset.tab)));
            return _panel;
        }

        function switchTab(tabName) {
            const p = _ensurePanel();
            p.querySelectorAll('.ti-tab').forEach(b =>
                b.classList.toggle('active', b.dataset.tab === tabName));
            p.querySelectorAll('.ti-tab-panel').forEach(panel => {
                const active = panel.id === `ti-tab-${tabName}`;
                panel.classList.toggle('active', active);
                panel.hidden = !active;
            });
        }

        function open(nodeData) {
            const p = _ensurePanel();
            const details  = p.querySelector('#ti-tab-details');
            const diffPanel = p.querySelector('#ti-tab-diff');
            const title    = p.querySelector('#ti-title');

            if (title) title.textContent = nodeData.id || 'Task';

            if (details) {
                details.innerHTML = `
                    <dl class="ti-detail-list">
                        <dt>Status</dt>
                        <dd><span class="status-chip status-${(nodeData.status||'').toLowerCase()}">${nodeData.status||'—'}</span></dd>
                        <dt>Agent</dt><dd>${nodeData.agent_type||'—'}</dd>
                        <dt>Retries</dt><dd>${nodeData.retry_count ?? 0}</dd>
                        <dt>Commit</dt><dd><code>${nodeData.commit_sha||'—'}</code></dd>
                        <dt>Error</dt><dd class="ti-error-text">${nodeData.error||'—'}</dd>
                    </dl>`;
            }

            if (diffPanel) {
                diffPanel.innerHTML = '<p class="ti-empty">Loading diff…</p>';
                const proj = nodeData.project_name;
                const fp   = nodeData.id;
                if (proj && fp) {
                    fetch(`/api/projects/${encodeURIComponent(proj)}/git/diff/${encodeURIComponent(fp)}`)
                        .then(r => r.ok ? r.json() : null)
                        .then(data => {
                            if (!data || !data.diff) {
                                diffPanel.innerHTML = '<p class="ti-empty">No diff available.</p>';
                                return;
                            }
                            if (global.DiffViewer) {
                                diffPanel.innerHTML = '';
                                diffPanel.appendChild(global.DiffViewer.render(data.diff));
                            } else {
                                diffPanel.innerHTML = `<pre class="ti-diff-raw">${_esc(data.diff)}</pre>`;
                            }
                        })
                        .catch(() => { diffPanel.innerHTML = '<p class="ti-empty">Could not load diff.</p>'; });
                } else {
                    diffPanel.innerHTML = '<p class="ti-empty">No file path available.</p>';
                }
            }

            switchTab('details');
            p.classList.add('open');
        }

        function close() { if (_panel) _panel.classList.remove('open'); }

        function _esc(s) {
            return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }

        return { open, close, switchTab };
    })();

    // Expose
    global.HITLModal     = HITLModal;
    global.TaskInspector = TaskInspector;

})(window);
