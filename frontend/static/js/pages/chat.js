/**
 * Chat Page Module for Ollash Agent
 * Handles UI logic specific to the chat view (prompt library, agent cards, etc.)
 */
window.ChatPageModule = (function() {
    let chatInput, chatMessages, sendBtn, promptLibraryToggle, promptLibraryPanel, promptCatBtns;
    let refactorCodeBtn, editStructureBtn, saveFileBtn;

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
        
        refactorCodeBtn = document.getElementById('refactor-code-btn');
        editStructureBtn = document.getElementById('edit-structure-btn');
        saveFileBtn = document.getElementById('save-file-btn');

        // Initial setup
        if (promptLibraryToggle) {
            promptLibraryToggle.addEventListener('click', togglePromptLibrary);
        }

        promptCatBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                promptCatBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                renderPromptLibrary(this.dataset.cat);
            });
        });

        if (refactorCodeBtn) {
            refactorCodeBtn.addEventListener('click', handleRefactorClick);
        }

        const addCollaboratorBtn = document.getElementById('add-collaborator-btn');
        if (addCollaboratorBtn) {
            addCollaboratorBtn.addEventListener('click', handleAddCollaborator);
        }

        const clearChatBtn = document.getElementById('clear-chat-btn');
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', handleClearChat);
        }

        console.log("🚀 ChatPageModule initialized");
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
                // Set agent type globally in ChatModule state if possible, or just click card
                const agentCard = document.querySelector(`.agent-card[data-agent="${p.agent}"]`);
                if (agentCard) agentCard.click();
                
                togglePromptLibrary();
            });
            grid.appendChild(card);
        });
    }

    function handleRefactorClick() {
        if (typeof monacoEditor === 'undefined' || !window.monacoEditor) {
            if (window.notificationService) notificationService.warning('Please open a file in the editor first.');
            return;
        }
        // Logic for refactoring from editor...
        // Simplified for now:
        const selection = window.monacoEditor.getSelection();
        if (selection && !selection.isEmpty()) {
            const text = window.monacoEditor.getModel().getValueInRange(selection);
            if (window.ChatModule) {
                document.querySelector('[data-view="chat"]').click();
                window.ChatModule.sendChatMessage(`Refactor this code:\n\n${text}`, 'code');
            }
        }
    }

    function handleAddCollaborator() {
        const agentType = prompt('Enter agent type to add (code, network, system, cybersecurity):');
        if (agentType && window.ChatModule) {
            window.ChatModule.sendChatMessage(`/add_collaborator ${agentType}`, 'orchestrator');
        }
    }

    function handleClearChat() {
        if (typeof window.showConfirmModal === 'function') {
            window.showConfirmModal(
                '¿Estás seguro de que quieres borrar el historial de chat?',
                () => {
                    if (chatMessages) {
                        chatMessages.innerHTML = `
                            <div class="chat-welcome">
                                <h2>Ollash Agent</h2>
                                <p>Select a specialist or start typing to use the auto-routing orchestrator.</p>
                            </div>
                        `;
                    }
                    if (window.notificationService) notificationService.info('Chat cleared');
                }
            );
        } else {
            // Fallback if modal not available yet
            if (confirm('Are you sure you want to clear the chat history?') && chatMessages) {
                chatMessages.innerHTML = `
                    <div class="chat-welcome">
                        <h2>Ollash Agent</h2>
                        <p>Select a specialist or start typing to use the auto-routing orchestrator.</p>
                    </div>
                `;
                if (window.notificationService) notificationService.info('Chat cleared');
            }
        }
    }

    return {
        init: init
    };
})();
