/**
 * DebateRoom — P8 Consensus/Debate Nodes UI
 *
 * Renders a split-screen overlay for DEBATE nodes.
 * Responds to SSE events: debate_round_completed, debate_consensus_reached.
 *
 * API:
 *   DebateRoom.open(nodeId)
 *   DebateRoom.close()
 *   DebateRoom.appendMessage(round, agentRole, agentId, argument)
 *   DebateRoom.showConsensus(text)
 */
(function (global) {
    'use strict';

    let _overlay = null;
    let _panelA  = null;
    let _panelB  = null;

    function _ensureOverlay() {
        if (_overlay) return _overlay;

        _overlay = document.createElement('div');
        _overlay.id = 'debate-room-overlay';
        _overlay.className = 'debate-overlay';
        _overlay.setAttribute('hidden', '');
        _overlay.innerHTML = `
            <div class="debate-modal">
                <div class="debate-header">
                    <div class="debate-header-badge">Debate Room</div>
                    <span class="debate-node-id" id="debate-node-id-label"></span>
                    <button class="debate-close-btn" id="debate-close-btn">&times;</button>
                </div>
                <div class="debate-split">
                    <div class="debate-panel" id="debate-panel-a">
                        <div class="debate-panel-header">Agent A</div>
                        <div class="debate-messages" id="debate-messages-a"></div>
                    </div>
                    <div class="debate-divider"></div>
                    <div class="debate-panel" id="debate-panel-b">
                        <div class="debate-panel-header">Agent B</div>
                        <div class="debate-messages" id="debate-messages-b"></div>
                    </div>
                </div>
                <div class="debate-consensus" id="debate-consensus" hidden>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span id="debate-consensus-text"></span>
                </div>
            </div>`;
        document.body.appendChild(_overlay);

        _overlay.querySelector('#debate-close-btn').addEventListener('click', close);
        _panelA = _overlay.querySelector('#debate-messages-a');
        _panelB = _overlay.querySelector('#debate-messages-b');
        return _overlay;
    }

    function open(nodeId) {
        const ov = _ensureOverlay();
        const label = ov.querySelector('#debate-node-id-label');
        if (label) label.textContent = nodeId || '';
        if (_panelA) _panelA.innerHTML = '';
        if (_panelB) _panelB.innerHTML = '';
        const c = ov.querySelector('#debate-consensus');
        if (c) c.setAttribute('hidden', '');
        ov.removeAttribute('hidden');
    }

    function close() {
        if (_overlay) _overlay.setAttribute('hidden', '');
    }

    function appendMessage(round, agentRole, agentId, argument) {
        const isA = ['a', 'A', 'agent_a'].includes(String(agentRole));
        const panel = isA ? _panelA : _panelB;
        if (!panel) return;

        const bubble = document.createElement('div');
        bubble.className = 'debate-bubble';
        bubble.innerHTML = `
            <div class="debate-bubble-meta">Round ${round} — ${agentId || agentRole}</div>
            <div class="debate-bubble-text">${_esc(argument || '')}</div>`;
        panel.appendChild(bubble);
        panel.scrollTop = panel.scrollHeight;
    }

    function showConsensus(text) {
        if (!_overlay) return;
        const c   = _overlay.querySelector('#debate-consensus');
        const txt = _overlay.querySelector('#debate-consensus-text');
        if (c)   c.removeAttribute('hidden');
        if (txt) txt.textContent = text || 'Consensus reached.';
    }

    function _esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    global.DebateRoom = { open, close, appendMessage, showConsensus };
})(window);
