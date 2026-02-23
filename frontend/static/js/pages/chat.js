/**
 * Chat Page Module for Ollash Agent
 * Handles UI logic specific to the chat view (prompt library, agent cards, toolbox, etc.)
 */
window.ChatPageModule = (function() {
    let chatInput, chatMessages, sendBtn, promptLibraryToggle, promptLibraryPanel, promptCatBtns;
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
        promptLibraryPanel = document.getElementById('prompt-library-panel');
        promptCatBtns = document.querySelectorAll('.prompt-cat-btn');
        
        toolboxContent = document.getElementById('toolbox-content');
        toolboxTotalCount = document.getElementById('toolbox-total-count');
        toolboxSearchInput = document.getElementById('toolbox-search-input');

        // Initial setup
        if (promptLibraryToggle) {
            promptLibraryToggle.addEventListener('click', togglePromptLibrary);
        }

        const closePromptsBtn = document.getElementById('close-prompts-btn');
        if (closePromptsBtn) {
            closePromptsBtn.addEventListener('click', () => {
                promptLibraryPanel.style.display = 'none';
            });
        }

        promptCatBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                promptCatBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                renderPromptLibrary(this.dataset.cat);
            });
        });

        const addCollaboratorBtn = document.getElementById('add-collaborator-btn');
        if (addCollaboratorBtn) {
            addCollaboratorBtn.addEventListener('click', handleAddCollaborator);
        }

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
        
        // Sort categories to show important ones first
        const sortedCats = Object.keys(categories).sort();
        
        sortedCats.forEach(cat => {
            const tools = categories[cat];
            const catDiv = document.createElement('div');
            catDiv.className = 'toolbox-category';
            catDiv.innerHTML = `
                <div class="toolbox-category-header">
                    <span class="toolbox-category-name">${cat}</span>
                    <span class="toolbox-category-count">${tools.length}</span>
                </div>
                <div class="toolbox-category-items"></div>
            `;
            
            const itemsContainer = catDiv.querySelector('.toolbox-category-items');
            tools.forEach(tool => {
                const toolDiv = document.createElement('div');
                toolDiv.className = 'toolbox-item';
                toolDiv.title = tool.description;
                toolDiv.innerHTML = `
                    <div class="toolbox-item-name">${tool.name}</div>
                    <div class="toolbox-item-desc">${tool.description}</div>
                `;
                toolDiv.addEventListener('click', () => {
                    if (chatInput) {
                        chatInput.value = `How do I use the ${tool.name} tool?`;
                        chatInput.focus();
                    }
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
        
        // Hide empty categories
        document.querySelectorAll('.toolbox-category').forEach(cat => {
            const visibleItems = cat.querySelectorAll('.toolbox-item[style="display: block;"]').length;
            const allItems = cat.querySelectorAll('.toolbox-item').length;
            const queryEmpty = query === '';
            
            if (queryEmpty) {
                cat.style.display = 'block';
            } else {
                cat.style.display = visibleItems > 0 ? 'block' : 'none';
            }
        });
    }

    function togglePromptLibrary() {
        if (!promptLibraryPanel) return;
        const isHidden = promptLibraryPanel.style.display === 'none';
        promptLibraryPanel.style.display = isHidden ? 'block' : 'none';
        if (isHidden) {
            promptLibraryPanel.classList.add('visible');
            renderPromptLibrary();
        } else {
            promptLibraryPanel.classList.remove('visible');
        }
    }

    function renderPromptLibrary(filter = 'all') {
        const grid = document.getElementById('prompt-library-list');
        if (!grid) return;
        grid.innerHTML = '';
        const filtered = filter === 'all' ? PROMPT_LIBRARY : PROMPT_LIBRARY.filter(p => p.category === filter);
        filtered.forEach(p => {
            const card = document.createElement('div');
            card.className = 'prompt-card';
            card.innerHTML = `
                <div class="prompt-card-label">${escapeHtml(p.label)}</div>
                <div class="prompt-card-cat">${escapeHtml(p.category)}</div>
            `;
            card.addEventListener('click', () => {
                if (chatInput) {
                    chatInput.value = p.prompt;
                    chatInput.style.height = 'auto';
                    chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
                    chatInput.focus();
                }
                const agentCard = document.querySelector(`.agent-card[data-agent="${p.agent}"]`);
                if (agentCard) agentCard.click();
                togglePromptLibrary();
            });
            grid.appendChild(card);
        });
    }

    function handleAddCollaborator() {
        const agentType = prompt('Enter agent type to add (code, network, system, cybersecurity):');
        if (agentType && window.ChatModule) {
            window.ChatModule.sendChatMessage(`/add_collaborator ${agentType}`, 'orchestrator');
        }
    }

    function handleClearChat() {
        if (confirm('Are you sure you want to clear the chat history?') && chatMessages) {
            chatMessages.innerHTML = `
                <div class="chat-welcome">
                    <h2>Ollash Agent</h2>
                    <p>Select a specialist or start typing to use the auto-routing orchestrator.</p>
                </div>
            `;
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return {
        init: init
    };
})();
