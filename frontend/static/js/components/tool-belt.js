/**
 * ToolBelt — P9 Dynamic Tool Usage UI
 *
 * Shows per-agent tool icon strips in the swimlane area.
 * Responds to SSE events: tool_execution_started, tool_execution_completed.
 *
 * API:
 *   ToolBelt.init(containerSelector)
 *   ToolBelt.onToolStarted(data)     — { agent_id, tool_name, task_id }
 *   ToolBelt.onToolCompleted(data)   — { agent_id, tool_name, duration_ms }
 *   ToolBelt.clearLane(agentId)
 */
(function (global) {
    'use strict';

    const KNOWN_TOOLS = {
        file_content_generator: { label: 'File Gen',  icon: '📄' },
        code_patcher:           { label: 'Patcher',   icon: '🔧' },
        rag_context_selector:   { label: 'RAG',       icon: '🔍' },
        vulnerability_scanner:  { label: 'SecScan',   icon: '🛡️' },
        code_quarantine:        { label: 'Quarantine',icon: '🔒' },
        infra_generator:        { label: 'Infra',     icon: '🏗️' },
        dependency_graph:       { label: 'DepGraph',  icon: '🕸️' },
        structure_generator:    { label: 'Structure', icon: '🗂️' },
        sandbox_runner:         { label: 'Sandbox',   icon: '⚗️' },
    };

    let _container = null;
    const _lanes   = {};   // agentId → { el, tools: { toolName → iconEl } }

    function init(containerSelector) {
        _container = typeof containerSelector === 'string'
            ? document.querySelector(containerSelector)
            : containerSelector;
    }

    function _ensureLane(agentId) {
        if (_lanes[agentId]) return _lanes[agentId];

        const lane = document.createElement('div');
        lane.className = 'tool-belt-lane';
        lane.dataset.agentId = agentId;
        lane.innerHTML = `
            <div class="tool-belt-agent-name">${agentId}</div>
            <div class="tool-belt-tools" id="tools-${_sid(agentId)}"></div>`;

        if (_container) _container.appendChild(lane);
        _lanes[agentId] = { el: lane, tools: {} };
        return _lanes[agentId];
    }

    function _ensureTool(laneData, toolName) {
        if (laneData.tools[toolName]) return laneData.tools[toolName];

        const meta     = KNOWN_TOOLS[toolName] || { label: toolName, icon: '⚙️' };
        const toolsEl  = laneData.el.querySelector('.tool-belt-tools');
        if (!toolsEl) return null;

        const iconEl = document.createElement('div');
        iconEl.className = 'tool-belt-icon';
        iconEl.title = meta.label;
        iconEl.innerHTML = `
            <span class="tb-emoji">${meta.icon}</span>
            <div class="tool-belt-tooltip">${meta.label}</div>`;

        toolsEl.appendChild(iconEl);
        laneData.tools[toolName] = iconEl;
        return iconEl;
    }

    function onToolStarted(data) {
        const { agent_id, tool_name } = data;
        if (!agent_id || !tool_name) return;
        const icon = _ensureTool(_ensureLane(agent_id), tool_name);
        if (!icon) return;
        icon.classList.add('active');
        icon.classList.remove('done');
    }

    function onToolCompleted(data) {
        const { agent_id, tool_name, duration_ms } = data;
        if (!agent_id || !tool_name) return;
        const lane = _lanes[agent_id];
        if (!lane) return;
        const icon = lane.tools[tool_name];
        if (!icon) return;

        icon.classList.remove('active');
        icon.classList.add('done');

        const tip = icon.querySelector('.tool-belt-tooltip');
        if (tip && duration_ms) {
            tip.textContent = `${KNOWN_TOOLS[tool_name]?.label || tool_name} (${duration_ms}ms)`;
        }
        setTimeout(() => icon.classList.remove('done'), 3000);
    }

    function clearLane(agentId) {
        const lane = _lanes[agentId];
        if (lane) { lane.el.remove(); delete _lanes[agentId]; }
    }

    function _sid(s) { return s.replace(/[^a-zA-Z0-9_-]/g, '_'); }

    global.ToolBelt = { init, onToolStarted, onToolCompleted, clearLane };
})(window);
