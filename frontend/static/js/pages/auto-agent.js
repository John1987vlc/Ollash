/**
 * AutoAgent Kanban Board
 * Manages the Kanban board UI for agile task visualization.
 * Extracted from auto_agent.html inline script.
 */
window.KanbanBoard = (function () {
    function updateCounters() {
        ['todo', 'in_progress', 'done'].forEach(status => {
            const container = document.getElementById(`tasks-${status}`);
            const countEl = document.getElementById(`count-${status}`);
            if (container && countEl) {
                countEl.textContent = `(${container.children.length})`;
            }
        });
    }

    function addTaskToColumn(task, status) {
        const container = document.getElementById(`tasks-${status}`);
        if (!container) return;

        const card = document.createElement('div');
        card.className = `kanban-card ${status}`;
        card.id = `task-card-${task.id}`;
        card.innerHTML = `
            <h4>${task.title}</h4>
            <p>${task.description || ''}</p>
            <div style="font-size:0.7rem;margin-top:8px;opacity:0.6;font-family:monospace;">${task.file_path || ''}</div>
        `;
        container.appendChild(card);
    }

    function initBacklog(tasks) {
        const board = document.getElementById('kanban-board');
        if (board) board.style.display = 'flex';

        ['todo', 'in_progress', 'done'].forEach(status => {
            const el = document.getElementById(`tasks-${status}`);
            if (el) el.innerHTML = '';
        });

        tasks.forEach(task => addTaskToColumn(task, task.status || 'todo'));
        updateCounters();
    }

    function moveTask(taskId, newStatus) {
        const card = document.getElementById(`task-card-${taskId}`);
        const dest = document.getElementById(`tasks-${newStatus}`);
        if (!card || !dest) return;

        card.classList.remove('todo', 'in_progress', 'done', 'waiting');
        card.classList.add(newStatus);
        dest.appendChild(card);
        updateCounters();
    }

    function addTaskToColumn(task, status) {
        const container = document.getElementById(`tasks-${status}`);
        if (!container) return;

        const card = document.createElement('div');
        card.className = `kanban-card ${status}`;
        card.id = `task-card-${task.id}`;
        card.dataset.nodeId = task.id;
        card.innerHTML = `
            <h4>${task.title || task.id}</h4>
            <p>${task.description || ''}</p>
            <div style="font-size:0.7rem;margin-top:8px;opacity:0.6;font-family:monospace;">${task.file_path || task.agent_type || ''}</div>
        `;
        // P6 — click → TaskInspector
        card.addEventListener('click', () => {
            if (window.TaskInspector) {
                window.TaskInspector.open({
                    id: task.id,
                    status: task.status || status,
                    agent_type: task.agent_type || '',
                    retry_count: task.retry_count || 0,
                    commit_sha: task.commit_sha || '',
                    error: task.error || '',
                    project_name: window._currentProjectName || '',
                });
            }
        });
        container.appendChild(card);
    }

    return { initBacklog, moveTask, addTaskToColumn };
}());

// ---------------------------------------------------------------------------
// P1-P10: SSE Event Wiring
// ---------------------------------------------------------------------------

(function () {
    'use strict';

    // ---- Initialise component containers once DOM is ready ----
    document.addEventListener('DOMContentLoaded', () => {
        if (window.ToolBelt)    window.ToolBelt.init('#agent-swimlanes');
        if (window.StreamPanel) window.StreamPanel.init('#stream-panels-container');
    });

    // ---- Budget meter helpers ----
    const BUDGET_LIMIT = 500_000;

    function updateBudgetMeter(usedTokens) {
        const meter  = document.getElementById('budget-meter');
        const bar    = document.getElementById('budget-meter-bar');
        const text   = document.getElementById('budget-meter-text');
        if (!meter) return;

        meter.removeAttribute('hidden');
        const pct = Math.min(100, Math.round((usedTokens / BUDGET_LIMIT) * 100));
        if (bar) {
            bar.style.width = pct + '%';
            bar.classList.remove('warn', 'limit');
            if (pct >= 90)      bar.classList.add('limit');
            else if (pct >= 70) bar.classList.add('warn');
        }
        if (text) {
            const fmt = n => n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n);
            text.textContent = `${fmt(usedTokens)} / ${fmt(BUDGET_LIMIT)}`;
        }
    }

    function showBudgetAlert() {
        const existing = document.querySelector('.budget-alert-banner');
        if (existing) return;
        const banner = document.createElement('div');
        banner.className = 'budget-alert-banner';
        banner.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            Token budget exceeded — DAG paused for review.
            <button class="close-alert" onclick="this.parentElement.remove()">&times;</button>`;
        document.body.appendChild(banner);
        setTimeout(() => banner.remove(), 12_000);
    }

    // ---- SSE event → component dispatch ----
    function handleAutoAgentEvent(eventType, data) {
        switch (eventType) {

            // P4 — streaming token chunks
            case 'blackboard_stream_chunk':
                if (window.StreamPanel) {
                    window.StreamPanel.onChunk(data.rel_path, data.chunk, data.agent_id);
                }
                break;

            // file_generated finalizes the stream panel
            case 'file_generated':
                if (window.StreamPanel) {
                    window.StreamPanel.finalize(data.file_path);
                }
                break;

            // P5 — budget
            case 'budget_exceeded':
                updateBudgetMeter(data.used_tokens || 0);
                showBudgetAlert();
                break;

            // P1 — HITL pause
            case 'hitl_requested':
                if (window.HITLModal) {
                    window.HITLModal.show(
                        data.task_id || data.node_id,
                        data.agent_id || 'agent',
                        data.question || data.message || 'Agent requires your input.'
                    );
                }
                break;

            // P9 — Tool Belt
            case 'tool_execution_started':
                if (window.ToolBelt) window.ToolBelt.onToolStarted(data);
                break;
            case 'tool_execution_completed':
                if (window.ToolBelt) window.ToolBelt.onToolCompleted(data);
                // Also update budget display if token counts arrive here
                if (data.total_tokens) updateBudgetMeter(data.total_tokens);
                break;

            // P8 — Debate nodes
            case 'debate_round_completed':
                if (window.DebateRoom) {
                    if (!document.getElementById('debate-room-overlay') ||
                        document.getElementById('debate-room-overlay').hasAttribute('hidden')) {
                        window.DebateRoom.open(data.node_id);
                    }
                    window.DebateRoom.appendMessage(
                        data.round, data.agent_role, data.agent_id, data.argument
                    );
                }
                break;
            case 'debate_consensus_reached':
                if (window.DebateRoom) window.DebateRoom.showConsensus(data.consensus_text);
                break;

            // P6 — git commit notification (update kanban card badge)
            case 'file_committed': {
                const sha = data.commit_sha || '';
                const fp  = data.file_path  || '';
                if (sha && fp) {
                    const card = document.getElementById(`task-card-${fp}`);
                    if (card) {
                        const badge = document.createElement('span');
                        badge.style.cssText = 'font-size:0.65rem;font-family:monospace;opacity:0.6;';
                        badge.textContent = ` ✓ ${sha}`;
                        card.querySelector('h4')?.appendChild(badge);
                    }
                }
                break;
            }

            default:
                break;
        }
    }

    // Patch onto global so projects.js (which owns the SSE connection) can call it
    window._autoAgentEventHandler = handleAutoAgentEvent;

})();
