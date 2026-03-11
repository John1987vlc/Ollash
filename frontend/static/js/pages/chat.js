/**
 * Chat Page Module for Ollash Agent
 * Handles UI logic specific to the chat view (prompt library, agent cards, toolbox, etc.)
 */
window.ChatPageModule = (function() {
    let chatInput, chatMessages, sendBtn, promptLibraryToggle, promptLibraryPanel;
    let toolboxContent, toolboxTotalCount, toolboxSearchInput;

    const PROMPT_LIBRARY = [
        { category: 'system', label: 'Disk Usage Report', agent: 'system', prompt: 'Check disk usage on all mounted volumes and report any partitions above 80% utilization.' },
        { category: 'system', label: 'Service Status Check', agent: 'system', prompt: 'List all running services and identify any that have failed or are in a degraded state.' },
        { category: 'system', label: 'Process Monitor', agent: 'system', prompt: 'Show the top 10 processes by CPU and memory usage. Identify any anomalies.' },
        { category: 'network', label: 'Latency Diagnostic', agent: 'network', prompt: 'Run a latency diagnostic to common DNS servers and major websites. Report any packet loss.' },
        { category: 'network', label: 'Port Scan', agent: 'network', prompt: 'Scan open ports on localhost and identify any unexpected services listening.' },
        { category: 'network', label: 'DNS Resolution', agent: 'network', prompt: 'Check DNS resolution for common domains and identify any DNS issues.' },
        { category: 'security', label: 'Permission Audit', agent: 'cybersecurity', prompt: 'Audit file permissions in the current project directory. Identify any world-writable files or insecure permissions.' },
        { category: 'security', label: 'Dependency Vulnerabilities', agent: 'cybersecurity', prompt: 'Check project dependencies for known vulnerabilities and suggest updates.' },
        { category: 'security', label: 'Secret Scanner', agent: 'cybersecurity', prompt: 'Scan the current project for hardcoded secrets, API keys, or credentials that should be in environment variables.' },
        { category: 'code', label: 'Code Quality Review', agent: 'code', prompt: 'Analyze the project code for common anti-patterns, code smells, and suggest improvements.' },
        { category: 'code', label: 'Test Coverage', agent: 'code', prompt: 'Analyze the project test coverage and suggest areas that need additional testing.' },
        { category: 'code', label: 'Documentation Check', agent: 'code', prompt: 'Check if all public functions and classes have proper docstrings and documentation.' },
    ];

    function init() {
        // DOM Elements
        chatInput = document.getElementById('chat-input');
        chatMessages = document.getElementById('chat-messages');
        sendBtn = document.getElementById('send-btn');
        promptLibraryToggle = document.getElementById('toggle-prompt-library');
        promptLibraryPanel = document.getElementById('prompt-library-modal');
        
        toolboxContent = document.getElementById('toolbox-content');
        toolboxTotalCount = document.getElementById('toolbox-total-count');
        toolboxSearchInput = document.getElementById('toolbox-search-input');

        // Modal Elements V2
        const closePromptsBtn = document.getElementById('close-prompts-btn');
        const openAddBtn = document.getElementById('open-add-prompt-btn');
        const cancelAddBtn = document.getElementById('cancel-add-prompt');
        const addFormOverlay = document.getElementById('add-prompt-form');
        const addPromptBtn = document.getElementById('add-custom-prompt-btn');
        const filterPills = document.querySelectorAll('.filter-pill');
        const searchInput = document.getElementById('prompt-search-input');

        if (promptLibraryToggle) {
            promptLibraryToggle.onclick = () => {
                promptLibraryPanel.style.display = 'flex';
                renderPromptLibrary();
            };
        }

        if (closePromptsBtn) {
            closePromptsBtn.onclick = () => promptLibraryPanel.style.display = 'none';
        }

        if (openAddBtn) {
            openAddBtn.onclick = () => addFormOverlay.style.display = 'flex';
        }

        if (cancelAddBtn) {
            cancelAddBtn.onclick = () => addFormOverlay.style.display = 'none';
        }

        if (addPromptBtn) {
            addPromptBtn.onclick = () => {
                const label = document.getElementById('custom-prompt-label').value;
                const prompt = document.getElementById('custom-prompt-text').value;
                if (label && prompt) {
                    PROMPT_LIBRARY.unshift({ category: 'custom', label, prompt, agent: 'orchestrator' });
                    renderPromptLibrary();
                    addFormOverlay.style.display = 'none';
                    document.getElementById('custom-prompt-label').value = '';
                    document.getElementById('custom-prompt-text').value = '';
                }
            };
        }

        if (searchInput) {
            searchInput.oninput = (e) => renderPromptLibrary(getActiveFilters(), e.target.value.toLowerCase());
        }

        filterPills.forEach(pill => {
            pill.onclick = function() {
                const cat = this.dataset.cat;
                if (cat === 'all') {
                    filterPills.forEach(p => p.classList.remove('active'));
                    this.classList.add('active');
                } else {
                    document.querySelector('.filter-pill[data-cat="all"]').classList.remove('active');
                    this.classList.toggle('active');
                    if (document.querySelectorAll('.filter-pill.active').length === 0) {
                        document.querySelector('.filter-pill[data-cat="all"]').classList.add('active');
                    }
                }
                renderPromptLibrary(getActiveFilters(), searchInput.value.toLowerCase());
            };
        });

        function getActiveFilters() {
            const active = Array.from(document.querySelectorAll('.filter-pill.active')).map(p => p.dataset.cat);
            return active.includes('all') ? 'all' : active;
        }
        
        // Attachments
        const fileInput = document.getElementById('chat-file-input');
        const previewContainer = document.getElementById('chat-attachment-preview');
        const attachBtn = document.getElementById('attach-file-btn');

        if (attachBtn && fileInput) {
            attachBtn.onclick = () => fileInput.click();
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    previewContainer.innerHTML = `
                        <div class="attachment-tag">
                            <span>📎 ${file.name}</span>
                            <span class="remove-btn" id="remove-attachment">✕</span>
                        </div>
                    `;
                    previewContainer.style.display = 'flex';
                    document.getElementById('remove-attachment').onclick = () => {
                        fileInput.value = '';
                        previewContainer.style.display = 'none';
                    };
                }
            };
        }

        const imageBtn = document.getElementById('generate-assets-btn');
        if (imageBtn) imageBtn.onclick = () => window.showMessage('Image generation active. Use /image in chat.', 'info');

        const voiceBtn = document.getElementById('voice-input-btn');
        if (voiceBtn) voiceBtn.onclick = () => window.showMessage('Voice initialization...', 'info');

        const clearChatBtn = document.getElementById('clear-chat-btn');
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', handleClearChat);
        }

        if (toolboxSearchInput) {
            toolboxSearchInput.addEventListener('input', (e) => {
                filterToolbox(e.target.value.toLowerCase());
            });
        }

        // Load Toolbox
        loadToolbox();

        console.log("🚀 ChatPageModule initialized");
    }

    async function loadToolbox() {
        if (!toolboxContent) return;
        try {
            const resp = await fetch('/api/analysis/tools/definitions');
            if (!resp.ok) throw new Error('Failed to load tools');
            const data = await resp.json();
            if (toolboxTotalCount) toolboxTotalCount.textContent = data.total_tools;
            renderToolbox(data.categories);
        } catch (err) {
            toolboxContent.innerHTML = `<div class="error-msg">Error loading tools: ${err.message}</div>`;
        }
    }

    function renderToolbox(categories) {
        if (!toolboxContent) return;
        toolboxContent.innerHTML = '';
        const sortedCats = Object.keys(categories).sort();
        sortedCats.forEach(cat => {
            const tools = categories[cat];
            const catDiv = document.createElement('div');
            catDiv.className = 'toolbox-category collapsed';
            catDiv.innerHTML = `
                <div class="toolbox-category-header">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="toolbox-chevron">›</span>
                        <span class="toolbox-category-name">${cat}</span>
                    </div>
                    <span class="toolbox-category-count">${tools.length}</span>
                </div>
                <div class="toolbox-category-items"></div>
            `;
            const header = catDiv.querySelector('.toolbox-category-header');
            header.onclick = () => catDiv.classList.toggle('collapsed');
            const itemsContainer = catDiv.querySelector('.toolbox-category-items');
            tools.forEach(tool => {
                const toolDiv = document.createElement('div');
                toolDiv.className = 'toolbox-item';
                toolDiv.title = tool.description;
                toolDiv.innerHTML = `<div class="toolbox-item-name">${tool.name}</div><div class="toolbox-item-desc">${tool.description}</div>`;
                toolDiv.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (chatInput) { chatInput.value = `How do I use the ${tool.name} tool?`; chatInput.focus(); }
                });
                itemsContainer.appendChild(toolDiv);
            });
            toolboxContent.appendChild(catDiv);
        });
    }

    function filterToolbox(query) {
        const items = document.querySelectorAll('.toolbox-item');
        items.forEach(item => {
            const name = item.querySelector('.toolbox-item-name').textContent.toLowerCase();
            const desc = item.querySelector('.toolbox-item-desc').textContent.toLowerCase();
            const matches = name.includes(query) || desc.includes(query);
            item.style.display = matches ? 'block' : 'none';
        });
        document.querySelectorAll('.toolbox-category').forEach(cat => {
            const visibleItems = cat.querySelectorAll('.toolbox-item[style="display: block;"]').length;
            cat.style.display = (query === '' || visibleItems > 0) ? 'block' : 'none';
        });
    }

    function renderPromptLibrary(filter = 'all', query = '') {
        const listContainer = document.getElementById('prompt-library-list');
        if (!listContainer) return;
        listContainer.innerHTML = '';
        const filtered = PROMPT_LIBRARY.filter(p => {
            const matchesCat = filter === 'all' || filter.includes(p.category);
            const matchesSearch = p.label.toLowerCase().includes(query) || p.prompt.toLowerCase().includes(query);
            return matchesCat && matchesSearch;
        });
        filtered.forEach(p => {
            const item = document.createElement('div');
            item.className = 'prompt-item-v2';
            item.innerHTML = `<div class="prompt-item-header"><span class="prompt-item-title">${p.label}</span><span class="prompt-item-tag">${p.category}</span></div><div class="prompt-item-desc">${p.prompt}</div>`;
            item.onclick = () => {
                if (chatInput) {
                    chatInput.value = p.prompt;
                    chatInput.style.height = 'auto';
                    chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
                    chatInput.focus();
                }
                const agentCard = document.querySelector(`.agent-card[data-agent="${p.agent}"]`);
                if (agentCard) agentCard.click();
                promptLibraryPanel.style.display = 'none';
            };
            listContainer.appendChild(item);
        });
    }

    function handleClearChat() {
        if (window.ConfirmDialog) {
            window.ConfirmDialog.ask('Clear the current conversation?').then((confirmed) => {
                if (confirmed) performClearChat();
            });
        } else if (confirm('Clear the current conversation?')) {
            performClearChat();
        }
    }

    function performClearChat() {
        if (window.ChatModule && window.ChatModule.deleteCurrentSession) {
            window.ChatModule.deleteCurrentSession();
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return { init };
})();

// Feature 5: Live Task DAG Dashboard
window.DagPanel = (function () {
    const _nodes = {};

    function updateNode(data) {
        const taskId = data.task_id || data.id;
        if (!taskId) return;
        _nodes[taskId] = {
            id: taskId,
            status: data.status || 'unknown',
            agent_type: data.agent_type || '',
        };
        _render();
    }

    function _render() {
        const list = document.getElementById('dag-node-list');
        const empty = document.getElementById('dag-empty-msg');
        const counter = document.getElementById('dag-node-count');
        if (!list) return;
        const nodeArr = Object.values(_nodes);
        if (counter) counter.textContent = nodeArr.length;
        if (nodeArr.length === 0) {
            if (empty) empty.style.display = '';
            list.innerHTML = '';
            return;
        }
        if (empty) empty.style.display = 'none';
        list.innerHTML = nodeArr.map(n => {
            const isPending = n.status === 'PENDING';
            const editBtn = isPending
                ? `<button class="btn-badge-action" style="font-size:0.7rem;padding:2px 5px;" onclick="window.DagPanel.editInstruction('${_esc(n.id)}')">Edit</button>`
                : '';
            return `<div class="dag-node-card" style="font-size:0.78rem;padding:4px 6px;border-left:3px solid var(--color-accent,#7c3aed);margin-bottom:4px;display:flex;align-items:center;gap:6px;">
                <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${_esc(n.id)}">${_esc(n.id)}</span>
                <span class="toolbox-badge" style="font-size:0.65rem;">${_esc(n.status)}</span>
                ${editBtn}
            </div>`;
        }).join('');
    }

    function editInstruction(taskId) {
        const newInstruction = prompt('Edit task instruction:');
        if (!newInstruction || !newInstruction.trim()) return;
        fetch('/api/hil/edit-task/' + encodeURIComponent(taskId), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction: newInstruction.trim() }),
        })
            .then(r => r.json())
            .then(d => {
                if (d.status === 'updated') {
                    window.NotificationToast?.show('Task instruction updated', 'success');
                } else {
                    window.NotificationToast?.show('Could not update: ' + d.error, 'error');
                }
            })
            .catch(() => window.NotificationToast?.show('Network error updating task', 'error'));
    }

    function _esc(str) {
        const d = document.createElement('div');
        d.textContent = String(str);
        return d.innerHTML;
    }

    document.addEventListener('DOMContentLoaded', () => {
        const toggle = document.getElementById('dag-panel-toggle');
        const body = document.getElementById('dag-panel-body');
        if (toggle && body) {
            toggle.addEventListener('click', () => {
                body.style.display = body.style.display === 'none' ? 'block' : 'none';
            });
        }
    });

    return { updateNode, editInstruction };
})();
