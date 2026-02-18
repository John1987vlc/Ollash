document.addEventListener('DOMContentLoaded', function() {
    // ==================== DOM Elements ====================
    // Projects
    const createProjectFormContainer = document.querySelector('.create-form-container'); // Parent of the form
    const createProjectForm = document.getElementById('create-project-form');
    const generateStructureBtn = createProjectForm.querySelector('button[type="submit"]'); // Renamed submit button
    generateStructureBtn.querySelector('span').textContent = 'Generate Structure'; // Update button text
    generateStructureBtn.querySelector('svg path').setAttribute('d', 'M10 2L18 6V14L10 18L2 14V6L10 2Z'); // Reset icon if changed by previous replace
    generateStructureBtn.querySelector('svg path').setAttribute('stroke', 'currentColor');
    generateStructureBtn.querySelector('svg path').setAttribute('fill', 'none');

    const statusMessage = document.getElementById('status-message');
    const existingProjectsSelect = document.getElementById('existing-projects');
    const fileTreeList = document.getElementById('file-tree-list');
    const currentFileNameSpan = document.getElementById('current-file-name');
    const agentLogs = document.getElementById('agent-logs');
    const projectWorkspace = document.getElementById('project-workspace');
    const previewFrame = document.getElementById('preview-frame');
    const clearLogsBtn = document.getElementById('clear-logs');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const previewTab = document.getElementById('preview-tab');
    const codeTab = document.getElementById('code-tab');
    const issuesTabButton = document.querySelector('[data-tab="issues"]');
    const issuesTabContent = document.getElementById('issues-tab');
    const issuesListDiv = document.getElementById('issues-list');
    const monacoEditorContainer = document.getElementById('monaco-editor-container');
    const saveFileBtn = document.getElementById('save-file-btn');
    const refactorCodeBtn = document.getElementById('refactor-code-btn');
    const phaseTimelineContainer = document.getElementById('phase-timeline-container');
    const phaseSteps = document.querySelectorAll('.phase-step');
    const terminalTab = document.querySelector('[data-tab="terminal"]');
    const terminalTabContent = document.getElementById('terminal-tab');
    const terminalContainer = document.getElementById('terminal-container');

    // Wizard elements
    const wizardSteps = document.querySelectorAll('.wizard-step');
    const wizardIndicators = document.querySelectorAll('.wizard-step-indicator');
    const wizardNextBtns = document.querySelectorAll('.wizard-next-btn');
    const wizardBackBtns = document.querySelectorAll('.wizard-back-btn');
    const wizardGenerateBtn = document.getElementById('wizard-generate-btn');

    // Floating terminal elements
    const floatingTerminal = document.getElementById('floating-terminal');
    const toggleTerminalBtn = document.getElementById('toggle-terminal-btn');
    const terminalMinimizeBtn = document.getElementById('terminal-minimize-btn');
    const terminalMaximizeBtn = document.getElementById('terminal-maximize-btn');
    const terminalCloseBtn = document.getElementById('terminal-close-btn');
    const floatingTerminalHeader = floatingTerminal ? floatingTerminal.querySelector('.floating-terminal-header') : null;

    // Log filter elements
    const logFilterBtns = document.querySelectorAll('.log-filter-btn');

    // Health dashboard elements
    const healthCpuBar = document.getElementById('health-cpu-bar');
    const healthRamBar = document.getElementById('health-ram-bar');
    const healthGpuBar = document.getElementById('health-gpu-bar');
    const healthCpuVal = document.getElementById('health-cpu-val');
    const healthRamVal = document.getElementById('health-ram-val');
    const healthGpuVal = document.getElementById('health-gpu-val');
    const healthGpuMetric = document.getElementById('health-gpu-metric');

    // Prompt library elements
    const promptLibraryToggle = document.getElementById('prompt-library-toggle');
    const promptLibraryPanel = document.getElementById('prompt-library-panel');
    const promptCatBtns = document.querySelectorAll('.prompt-cat-btn');

    // Diff modal elements
    const diffModal = document.getElementById('diff-modal');
    const diffEditorContainer = document.getElementById('diff-editor-container');
    const diffFilePath = document.getElementById('diff-file-path');
    const diffApplyBtn = document.getElementById('diff-apply-btn');
    const diffDiscardBtn = document.getElementById('diff-discard-btn');

    // Minimap elements
    const minimapTab = document.getElementById('minimap-tab');
    const minimapContainer = document.getElementById('project-minimap-container');

    // New DOM elements for structure editor
    const generatedStructureSection = document.getElementById('generated-structure-section');
    const generatedFileTreeContainer = document.getElementById('generated-file-tree');
    const confirmStructureBtn = document.getElementById('confirm-structure-btn');
    const editStructureBtn = document.getElementById('edit-structure-btn');
    const addPathInput = document.getElementById('add-path-input');
    const addPathBtn = document.getElementById('add-path-btn');


    // Chat
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    // Benchmark
    const benchOllamaUrl = document.getElementById('bench-ollama-url');
    const benchFetchModels = document.getElementById('bench-fetch-models');
    const benchModelList = document.getElementById('bench-model-list');
    const benchStartBtn = document.getElementById('bench-start-btn');
    const benchOutput = document.getElementById('bench-output');
    const benchHistoryList = document.getElementById('bench-history-list');

    // Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    // ==================== State ====================
    let currentProject = null;
    let selectedFileElement = null;
    let logEventSource = null;
    let currentFilePath = null;
    let currentFileContent = null;
    let chatSessionId = null;
    let chatEventSource = null;
    let isChatBusy = false;
    let selectedAgentType = null;
    let benchEventSource = null;
    let selectedTemplate = 'default';

    // State for pre-generation structure editor
    let currentGeneratedStructure = null;
    let currentGeneratedReadme = null;
    let currentProjectName = null;
    let currentProjectDescription = null;
    let currentPythonVersion = null;
    let currentLicenseType = null;
    let currentIncludeDocker = null;

    let isEditorDirty = false; // Tracks if the current file in Monaco has unsaved changes
    let monacoEditor; // Global Monaco Editor instance
    let monacoModel; // Current Monaco Editor model
    let monacoDecorations = []; // Decorations for highlighting lines

    // Wizard state
    let currentWizardStep = 1;

    // Floating terminal state
    let floatingTerminalState = 'hidden'; // hidden, normal, minimized, maximized

    // Log filter state
    let activeLogFilter = 'all';

    // Diff editor state
    let diffEditor = null;
    let diffOriginalContent = '';
    let diffModifiedContent = '';
    let diffCurrentFilePath = '';

    // Structure editor instance
    let structureEditor = null;

    // Minimap network instance
    let minimapNetwork = null;

    // Xterm.js instance
    let term;
    let fitAddon;
    let currentCommand = '';
    const prompt = '\x1b[1;34m$ \x1b[0m'; // Blue dollar sign prompt

    // Helper to update visibility of editor action buttons
    function updateEditorActionButtons() {
        if (currentFilePath) {
            saveFileBtn.style.display = isEditorDirty ? 'inline-flex' : 'none';
            refactorCodeBtn.style.display = 'inline-flex';
        } else {
            saveFileBtn.style.display = 'none';
            refactorCodeBtn.style.display = 'none';
        }
    }

    // ==================== Navigation ====================
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            autoSaveCurrentFile(); // F10: Auto-save before navigation
            const viewId = this.dataset.view;
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
            views.forEach(view => view.classList.remove('active'));
            document.getElementById(`${viewId}-view`).classList.add('active');

            if (viewId === 'benchmark') loadBenchHistory();
        });
    });

    // ==================== Tab System ====================
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.dataset.tab;

            // F6: Terminal tab toggles floating terminal instead of switching tabs
            if (tabId === 'terminal') {
                toggleFloatingTerminal();
                return;
            }

            // F5: Minimap tab
            if (tabId === 'minimap') {
                tabBtns.forEach(tab => tab.classList.remove('active'));
                this.classList.add('active');
                previewTab.classList.remove('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.remove('active');
                if (minimapTab) minimapTab.classList.add('active');
                loadProjectMinimap();
                return;
            }

            autoSaveCurrentFile(); // F10: Auto-save on tab switch

            tabBtns.forEach(tab => tab.classList.remove('active'));
            this.classList.add('active');
            if (minimapTab) minimapTab.classList.remove('active');

            if (tabId === 'preview') {
                previewTab.classList.add('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.remove('active');
                updatePreview();
            } else if (tabId === 'code') {
                previewTab.classList.remove('active');
                codeTab.classList.add('active');
                issuesTabContent.classList.remove('active');
                if (monacoEditor) monacoEditor.layout();
            } else if (tabId === 'issues') {
                previewTab.classList.remove('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.add('active');
                loadProjectIssues(currentProject);
            }
        });
    });

    // ==================== Utilities ====================
    function showMessage(message, type = 'info') {
        statusMessage.textContent = message;
        statusMessage.className = `status-message ${type}`;
        statusMessage.style.display = 'block';
        setTimeout(() => { statusMessage.style.display = 'none'; }, 5000);
    }

    function addLogLine(message, type = 'info') {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${type}`;
        // F11: Determine log type for filtering
        let logType = type;
        if (message.includes('TOOL:') || message.startsWith('$') || message.includes('$ ')) {
            logType = 'cmd';
        }
        logLine.dataset.logType = logType;
        const timestamp = new Date().toLocaleTimeString();
        logLine.innerHTML = `<span style="opacity: 0.5">[${timestamp}]</span> ${escapeHtml(message)}`;
        // F11: Apply current filter
        if (activeLogFilter !== 'all' && logType !== activeLogFilter) {
            logLine.classList.add('filtered-out');
        }
        agentLogs.appendChild(logLine);
        agentLogs.scrollTop = agentLogs.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    clearLogsBtn.addEventListener('click', () => { agentLogs.innerHTML = ''; });

    // ==================== Template Selection ====================
    const templateCards = document.querySelectorAll('.template-card');
    templateCards.forEach(card => {
        card.addEventListener('click', function() {
            templateCards.forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            selectedTemplate = this.dataset.template;
        });
    });

    // ==================== Advanced Configuration ====================
    const toggleAdvancedConfigBtn = document.getElementById('toggle-advanced-config');
    const advancedConfigPanel = document.getElementById('advanced-config-panel');
    const advancedConfigToggleDiv = document.querySelector('.advanced-config-toggle');

    if (toggleAdvancedConfigBtn && advancedConfigPanel && advancedConfigToggleDiv) {
        toggleAdvancedConfigBtn.addEventListener('click', function() {
            const isHidden = advancedConfigPanel.style.display === 'none';
            advancedConfigPanel.style.display = isHidden ? 'block' : 'none';
            if (isHidden) {
                advancedConfigToggleDiv.classList.add('expanded');
            } else {
                advancedConfigToggleDiv.classList.remove('expanded');
            }
        });
    }

    // ==================== Chat ====================
    // Agent card selection
    document.querySelectorAll('.agent-card').forEach(card => {
        card.addEventListener('click', function() {
            selectedAgentType = this.dataset.agent;
            document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');
            const agentNames = {
                orchestrator: 'Orchestrator',
                code: 'Code Agent',
                network: 'Network Agent',
                system: 'System Agent',
                cybersecurity: 'Cybersecurity Agent'
            };
            chatInput.placeholder = `Ask the ${agentNames[selectedAgentType]}...`;
            chatInput.focus();
        });
    });

    function appendChatMessage(role, content) {
        const msg = document.createElement('div');
        msg.className = `chat-message ${role}`;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = content;
        msg.appendChild(bubble);
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return bubble;
    }

    function appendToolCard(toolName, args, index, total) {
        const card = document.createElement('div');
        card.className = 'tool-card';
        card.innerHTML = `
            <div class="tool-card-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="tool-icon">&#x1f527;</span>
                <span class="tool-name">${escapeHtml(toolName)}</span>
                <span class="tool-index">${index}/${total}</span>
                <span class="tool-chevron">&#x25B6;</span>
            </div>
            <div class="tool-card-body">
                <div class="tool-section">
                    <div class="tool-section-label">Arguments</div>
                    <pre class="tool-pre">${escapeHtml(JSON.stringify(args, null, 2))}</pre>
                </div>
                <div class="tool-result-section"></div>
            </div>
        `;
        chatMessages.appendChild(card);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return card;
    }

    function updateToolResult(card, name, success, resultText) {
        const section = card.querySelector('.tool-result-section');
        section.innerHTML = `
            <div class="tool-section">
                <div class="tool-section-label">${success ? '&#x2705; Result' : '&#x274c; Error'}</div>
                <pre class="tool-pre">${escapeHtml(resultText)}</pre>
            </div>
        `;
    }

    async function sendChatMessage(messageContent = null, agentTypeOverride = null) {
        const message = messageContent || chatInput.value.trim();
        const agentToSendAs = agentTypeOverride || selectedAgentType;

        if (!message || isChatBusy) return;

        isChatBusy = true;
        sendBtn.disabled = true;
        chatInput.value = '';
        chatInput.style.height = 'auto';
        selectedAgentType = agentToSendAs; // Ensure UI reflects the agent if overridden

        // Remove welcome message if present
        const welcome = chatMessages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        appendChatMessage('user', escapeHtml(message));

        try {
            const body = { message, session_id: chatSessionId };
            if (agentToSendAs) body.agent_type = agentToSendAs;

            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await resp.json();

            if (data.status !== 'started') {
                appendChatMessage('assistant', `<span class="chat-error">${escapeHtml(data.message)}</span>`);
                isChatBusy = false;
                sendBtn.disabled = false;
                return;
            }

            chatSessionId = data.session_id;

            // Open SSE stream
            if (chatEventSource) chatEventSource.close();
            chatEventSource = new EventSource(`/api/chat/stream/${chatSessionId}`);

            let currentToolCard = null;

            chatEventSource.onmessage = function(event) {
                let parsed;
                try { parsed = JSON.parse(event.data); } catch { return; }

                switch (parsed.type) {
                    case 'iteration':
                        break;

                    case 'tool_call':
                        currentToolCard = appendToolCard(
                            parsed.name, parsed.args, parsed.index, parsed.total
                        );
                        break;

                    case 'tool_result':
                        if (currentToolCard) {
                            updateToolResult(currentToolCard, parsed.name, parsed.success, parsed.result || '');
                            currentToolCard = null;
                        }
                        break;

                    case 'final_answer':
                        appendChatMessage('assistant', formatAnswer(parsed.content || ''));
                        break;

                    case 'error':
                        appendChatMessage('assistant',
                            `<span class="chat-error">${escapeHtml(parsed.message || 'Unknown error')}</span>`
                        );
                        break;

                    case 'stream_end':
                        chatEventSource.close();
                        chatEventSource = null;
                        isChatBusy = false;
                        sendBtn.disabled = false;
                        chatSessionId = null;
                        // Persist chat history to localStorage
                        if (typeof window._ollashSaveChatHook === 'function') {
                            window._ollashSaveChatHook();
                        }
                        break;
                }
            };

            chatEventSource.onerror = function() {
                chatEventSource.close();
                chatEventSource = null;
                isChatBusy = false;
                sendBtn.disabled = false;
                chatSessionId = null;
            };

        } catch (err) {
            appendChatMessage('assistant', `<span class="chat-error">Connection error: ${escapeHtml(err.message)}</span>`);
            isChatBusy = false;
            sendBtn.disabled = false;
        }
    }

    function formatAnswer(text) {
        let html = escapeHtml(text);

        // F7: Detect [REFACTOR:filepath] code blocks and render diff button
        html = html.replace(/\[REFACTOR:([^\]]+)\]\s*```([\s\S]*?)```/g, function(match, filepath, code) {
            const escapedPath = escapeHtml(filepath.trim());
            const escapedCode = code.trim();
            return `<div class="refactor-suggestion" data-filepath="${escapedPath}">
                <div class="refactor-header"><span class="diff-file-path">${escapedPath}</span>
                <button class="btn-secondary chat-diff-btn" data-filepath="${escapedPath}">Review Diff</button></div>
                <pre class="chat-code-block" style="display:none">${escapedCode}</pre>
            </div>`;
        });

        html = html
            .replace(/```([\s\S]*?)```/g, '<pre class="chat-code-block">$1</pre>')
            .replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>')
            .replace(/\n/g, '<br>');

        // F3: Parse [ACTION:label|agent_type|prompt] patterns into clickable buttons
        html = html.replace(/\[ACTION:([^|]+)\|([^|]+)\|([^\]]+)\]/g, function(match, label, agentType, prompt) {
            return `<button class="chat-action-btn" data-agent="${escapeHtml(agentType.trim())}" data-prompt="${escapeHtml(prompt.trim())}">${escapeHtml(label.trim())}</button>`;
        });

        return html;
    }

    sendBtn.addEventListener('click', sendChatMessage);

    // F3: Delegated click handler for chat action buttons
    chatMessages.addEventListener('click', function(e) {
        const actionBtn = e.target.closest('.chat-action-btn');
        if (actionBtn) {
            const prompt = actionBtn.dataset.prompt;
            const agentType = actionBtn.dataset.agent;
            if (prompt) sendChatMessage(prompt, agentType || null);
            return;
        }
        // F7: Delegated click handler for diff review buttons
        const diffBtn = e.target.closest('.chat-diff-btn');
        if (diffBtn) {
            const filepath = diffBtn.dataset.filepath;
            const codeBlock = diffBtn.closest('.refactor-suggestion').querySelector('.chat-code-block');
            if (codeBlock && filepath) {
                showDiffModal(filepath, codeBlock.textContent);
            }
        }
    });

    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });

    // Event listener for the "Ask Agent" button
    refactorCodeBtn.addEventListener('click', function() {
        if (!monacoEditor || !currentFilePath) {
            showMessage('Please open a file in the editor first.', 'warning');
            return;
        }

        const selection = monacoEditor.getSelection();
        let selectedText = '';
        let promptMessage = '';

        if (!selection.isEmpty()) {
            selectedText = monacoEditor.getModel().getValueInRange(selection);
            promptMessage = `Refactor the following code snippet from ${currentFilePath}:\n\`\`\`\n${selectedText}\n\`\`\`\nSuggest improvements or alternative implementations.`;
        } else {
            const position = monacoEditor.getPosition();
            if (position) {
                selectedText = monacoEditor.getModel().getLineContent(position.lineNumber);
                promptMessage = `Analyze the following line from ${currentFilePath}:\n\`\`\`\n${selectedText}\n\`\`\`\nWhat are your thoughts or suggestions for this line?`;
            } else {
                showMessage('No code selected or cursor position found.', 'warning');
                return;
            }
        }

        // Switch to chat view and send message
        document.querySelector('[data-view="chat"]').click();
        sendChatMessage(promptMessage, 'code'); // Send to the 'code' agent
    });

    // ==================== Project Creation Workflow ====================

    // This is the initial submission to generate the project structure
    createProjectForm.addEventListener('submit', handleGenerateStructureSubmit);

    async function handleGenerateStructureSubmit(event) {
        if (event) event.preventDefault();

        // F2: Read from wizard fields (they have the same IDs)
        currentProjectName = document.getElementById('project-name').value.trim();
        currentProjectDescription = document.getElementById('project-description').value.trim();

        if (!currentProjectName || !currentProjectDescription) {
            showMessage('Please fill in both project name and description.', 'error');
            return;
        }

        currentPythonVersion = document.getElementById('python-version').value;
        currentLicenseType = document.getElementById('license-type').value;
        currentIncludeDocker = document.getElementById('include-docker').checked;

        const formData = new FormData();
        formData.append('project_name', currentProjectName);
        formData.append('project_description', currentProjectDescription);
        formData.append('template_name', selectedTemplate);
        formData.append('python_version', currentPythonVersion);
        formData.append('license_type', currentLicenseType);
        formData.append('include_docker', currentIncludeDocker);

        showMessage('Generating project structure...', 'info');
        generateStructureBtn.disabled = true;

        try {
            const response = await fetch('/api/projects/generate_structure', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'structure_generated') {
                showMessage('Project structure generated successfully!', 'success');
                currentGeneratedStructure = data.structure;
                currentGeneratedReadme = data.readme;

                // Hide wizard/creation form, show structure editor
                const wizardContainer = document.querySelector('.wizard-container');
                if (wizardContainer) wizardContainer.style.display = 'none';
                if (createProjectFormContainer) createProjectFormContainer.style.display = 'none';
                generatedStructureSection.style.display = 'block';

                // F1: Use StructureEditor if available
                const seTree = document.getElementById('structure-editor-tree');
                if (typeof StructureEditor !== 'undefined' && seTree) {
                    structureEditor = new StructureEditor(seTree);
                    structureEditor.setStructure(currentGeneratedStructure);
                } else {
                    renderGeneratedFileTree(currentGeneratedStructure, generatedFileTreeContainer, true);
                }

            } else {
                showMessage(`Error generating structure: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showMessage('An error occurred while trying to generate the project structure.', 'error');
        } finally {
            generateStructureBtn.disabled = false;
        }
    }

    confirmStructureBtn.addEventListener('click', async function() {
        console.log('Confirm Structure button clicked. Initiating full project generation...');
        showMessage('Confirming structure and initiating full project generation...', 'info');

        // F1: Get structure from editor if available
        if (structureEditor) {
            currentGeneratedStructure = structureEditor.getStructure();
        }

        const formData = new FormData();
        formData.append('project_name', currentProjectName);
        formData.append('project_description', currentProjectDescription);
        formData.append('template_name', selectedTemplate);
        formData.append('python_version', currentPythonVersion);
        formData.append('license_type', currentLicenseType);
        formData.append('include_docker', currentIncludeDocker);
        formData.append('generated_structure', JSON.stringify(currentGeneratedStructure));
        formData.append('generated_readme', currentGeneratedReadme);

        confirmStructureBtn.disabled = true;
        editStructureBtn.disabled = true;

        try {
            const response = await fetch('/api/projects/create', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'started') {
                showMessage(`Project "${data.project_name}" is being created. Switching to Projects tab to view progress.`, 'success');
                await populateExistingProjects();
                setTimeout(() => {
                    document.querySelector('[data-view="projects"]').click();
                    existingProjectsSelect.value = data.project_name;
                    loadProject(data.project_name);
                }, 1000);
                // Reset form and UI
                createProjectForm.reset();
                const wizardContainer = document.querySelector('.wizard-container');
                if (wizardContainer) {
                    wizardContainer.style.display = 'block';
                    wizardGoTo(1); // Reset wizard to step 1
                }
                if (createProjectFormContainer) createProjectFormContainer.style.display = 'block';
                generatedStructureSection.style.display = 'none';
            } else {
                showMessage(`Error: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showMessage('An error occurred while trying to create the project.', 'error');
        } finally {
            confirmStructureBtn.disabled = false;
            editStructureBtn.disabled = false;
            generateStructureBtn.disabled = false; // Re-enable generate structure button
        }
    });

    editStructureBtn.addEventListener('click', function() {
        // This will be implemented in a later step
        console.log('Edit Structure button clicked.');
        showMessage('Edit Structure functionality is not yet fully implemented.', 'info');
    });

    // ==================== Project Listing ====================
    async function populateExistingProjects() {
        const currentValue = existingProjectsSelect.value;
        existingProjectsSelect.innerHTML = '<option value="">Select a project...</option>';

        try {
            const response = await fetch('/api/projects/list');
            if (response.ok) {
                const projects = await response.json();
                if (projects.status === 'success' && projects.projects.length > 0) {
                    projects.projects.forEach(project => {
                        const option = document.createElement('option');
                        option.value = project;
                        option.textContent = project;
                        existingProjectsSelect.appendChild(option);
                    });
                    if (currentValue && projects.projects.includes(currentValue)) {
                        existingProjectsSelect.value = currentValue;
                    }
                }
            }
        } catch (error) {
            console.error('Error populating projects:', error);
        }
    }

    existingProjectsSelect.addEventListener('change', function() {
        if (this.value) loadProject(this.value);
        else projectWorkspace.style.display = 'none';
    });

    // ==================== Load Project ====================
    async function loadProject(projectName) {
        currentProject = projectName;
        projectWorkspace.style.display = 'block';
        agentLogs.innerHTML = '';
        phaseTimelineContainer.style.display = 'flex'; // Make timeline visible
        resetPhaseTimeline(); // Reset all phases to pending

        if (logEventSource) { logEventSource.close(); logEventSource = null; }

        addLogLine(`Loading project: ${projectName}`, 'info');
        await fetchFileTree(projectName);
        startLogStream(projectName);
    }

    // Function to reset phase timeline
    function resetPhaseTimeline() {
        phaseSteps.forEach(step => {
            step.classList.remove('current', 'completed', 'error');
            step.classList.add('pending');
        });
        // Optionally set the first step as current or nothing
        if (phaseSteps.length > 0) {
            phaseSteps[0].classList.add('current');
            phaseSteps[0].classList.remove('pending');
        }
    }

    // Function to load project issues
    async function loadProjectIssues(projectName) {
        if (!projectName) {
            issuesListDiv.innerHTML = '<p class="issues-placeholder">Select a project to view issues.</p>';
            return;
        }
        issuesListDiv.innerHTML = '<p class="issues-placeholder">Loading issues...</p>';

        try {
            const response = await fetch(`/api/projects/${projectName}/issues`);
            const data = await response.json();

            if (data.status === 'success') {
                renderIssues(data.issues);
            } else {
                issuesListDiv.innerHTML = `<p class="issues-placeholder">Error loading issues: ${escapeHtml(data.message)}</p>`;
            }
        } catch (error) {
            console.error('Error loading project issues:', error);
            issuesListDiv.innerHTML = `<p class="issues-placeholder">An error occurred while loading issues.</p>`;
        }
    }

    // Function to render issues
    function renderIssues(issues) {
        issuesListDiv.innerHTML = ''; // Clear existing issues

        if (issues.length === 0) {
            issuesListDiv.innerHTML = '<p class="issues-placeholder">No issues found for this project yet.</p>';
            return;
        }

        issues.forEach(issue => {
            const issueCard = document.createElement('div');
            issueCard.className = `issue-card issue-${issue.severity.toLowerCase()}`;
            issueCard.dataset.filePath = issue.file; // Store file path
            issueCard.dataset.lineNumber = issue.line_number || 0; // Store line number if available (default to 0)

            issueCard.innerHTML = `
                <div class="issue-header">
                    <span class="issue-severity">${escapeHtml(issue.severity)}</span>
                    <span class="issue-file">${escapeHtml(issue.file || 'N/A')}${issue.line_number ? ':' + issue.line_number : ''}</span>
                </div>
                <div class="issue-description">${escapeHtml(issue.description)}</div>
                <div class="issue-recommendation">${escapeHtml(issue.recommendation)}</div>
            `;
            issuesListDiv.appendChild(issueCard);

            issueCard.addEventListener('click', function() {
                const filePath = this.dataset.filePath;
                const lineNumber = parseInt(this.dataset.lineNumber);
                if (filePath && currentProject) {
                    navigateToCodeLocation(filePath, lineNumber);
                } else {
                    showMessage('No specific file to navigate to for this issue.', 'warning');
                }
            });
        });
    }

    // ==================== Log Streaming ====================
    function startLogStream(projectName) {
        // Close any existing event source
        if (logEventSource) {
            logEventSource.close();
            logEventSource = null;
        }

        logEventSource = new EventSource(`/api/projects/stream/${projectName}`);

        logEventSource.onmessage = function(event) {
            let parsedEvent;
            try {
                parsedEvent = JSON.parse(event.data);
            } catch (e) {
                // Handle non-JSON keep-alive messages or old log lines
                if (event.data.startsWith(':')) return; // Keep-alive
                addLogLine(event.data, 'info'); // Treat as plain log
                return;
            }

            // Process structured events
            switch (parsedEvent.type) {
                case 'phase_start':
                    addLogLine(`PHASE ${parsedEvent.phase}: ${parsedEvent.message}...`, 'info');
                    updatePhaseTimeline(parsedEvent.phase, 'current');
                    break;
                case 'phase_complete':
                    addLogLine(`PHASE ${parsedEvent.phase} complete: ${parsedEvent.message}`, parsedEvent.status || 'success');
                    updatePhaseTimeline(parsedEvent.phase, parsedEvent.status || 'completed');
                    if (parsedEvent.phase === '2' || parsedEvent.phase === '3' || parsedEvent.phase === '4' || parsedEvent.phase === '5' || parsedEvent.phase === '5.5' || parsedEvent.phase === '5.6' || parsedEvent.phase === '5.7' || parsedEvent.phase === '7.5') {
                        if (!window._ftDebounce) {
                            window._ftDebounce = setTimeout(() => {
                                fetchFileTree(projectName);
                                window._ftDebounce = null;
                            }, 500);
                        }
                    }
                    break;
                case 'iteration_start':
                    addLogLine(`Iteration ${parsedEvent.iteration} started.`, 'info');
                    break;
                case 'iteration_end':
                    addLogLine(`Iteration ${parsedEvent.iteration} ended (${parsedEvent.status}).`, 'info');
                    break;
                case 'tool_start':
                    addLogLine(`  TOOL: ${parsedEvent.tool_name} started (File: ${parsedEvent.file || 'N/A'}) (Attempt: ${parsedEvent.attempt || 1})...`, 'info');
                    break;
                case 'tool_output':
                    let toolStatus = parsedEvent.status === 'success' ? 'success' : 'error';
                    let outputMsg = `  TOOL: ${parsedEvent.tool_name} finished (Status: ${parsedEvent.status})`;
                    if (parsedEvent.message) outputMsg += `: ${parsedEvent.message}`;
                    if (parsedEvent.file) outputMsg += ` (File: ${parsedEvent.file})`;
                    if (parsedEvent.error) outputMsg += ` (Error: ${parsedEvent.error})`;
                    if (parsedEvent.failures) outputMsg += ` (Failures: ${parsedEvent.failures.length})`;
                    addLogLine(outputMsg, toolStatus);
                    break;
                case 'tool_end':
                    // addLogLine(`  TOOL: ${parsedEvent.tool_name} ended.`, 'info'); // Might be too verbose
                    break;
                case 'project_complete':
                    addLogLine(`PROJECT COMPLETED: ${parsedEvent.project_name}!`, 'success');
                    fetchFileTree(projectName);
                    logEventSource.close();
                    logEventSource = null;
                    updatePhaseTimeline(8, 'completed');
                    // F9: Desktop notification on project completion
                    notificationService.showDesktop('Project Complete!', `${parsedEvent.project_name} has been generated successfully.`);
                    break;
                case 'error':
                    addLogLine(`ERROR: ${parsedEvent.message}`, 'error');
                    updatePhaseTimeline(parsedEvent.phase, 'error');
                    // F9: Desktop notification on error
                    notificationService.showDesktop('Error', parsedEvent.message || 'An error occurred during generation.');
                    break;
                case 'info':
                    addLogLine(`INFO: ${parsedEvent.message}`, 'info');
                    break;
                case 'warning':
                    addLogLine(`WARNING: ${parsedEvent.message}`, 'warning');
                    break;
                case 'debug':
                    addLogLine(`DEBUG: ${parsedEvent.message}`, 'debug');
                    break;
                case 'stream_end':
                    logEventSource.close();
                    logEventSource = null;
                    addLogLine('Project generation stream ended.', 'success');
                    fetchFileTree(projectName); // Final refresh
                    break;
                default:
                    addLogLine(`UNKNOWN EVENT (${parsedEvent.type}): ${JSON.stringify(parsedEvent)}`, 'info');
                    break;
            }
        };

        logEventSource.onerror = function(error) {
            console.error('EventSource failed:', error);
            logEventSource.close();
            logEventSource = null;
            addLogLine('Lost connection to project stream.', 'error');
        };
    }

    // Function to update the visual state of the phase timeline
    function updatePhaseTimeline(phase, status) {
        phaseSteps.forEach(step => {
            const stepPhase = parseInt(step.dataset.phase);
            step.classList.remove('current', 'completed', 'error');

            if (stepPhase < phase) {
                step.classList.add('completed');
            } else if (stepPhase === phase) {
                step.classList.add(status);
            } else {
                step.classList.add('pending');
            }
        });
        if (phaseSteps[phase -1]) {
            phaseTimelineContainer.scrollLeft = phaseSteps[phase -1].offsetLeft - (phaseTimelineContainer.offsetWidth / 2) + (phaseSteps[phase -1].offsetWidth / 2);
        }
    }

    // ==================== File Tree ====================
    async function fetchFileTree(projectName) {
        try {
            const response = await fetch(`/api/projects/${projectName}/files`);
            const data = await response.json();
            if (data.status === 'success') renderFileTree(data.files);
            else addLogLine(`Error loading file tree: ${data.message}`, 'error');
        } catch (error) {
            addLogLine('Error fetching file tree', 'error');
        }
    }

    function renderFileTree(files) {
        fileTreeList.innerHTML = '';
        const sorted = files.sort((a, b) => {
            if (a.type === 'directory' && b.type !== 'directory') return -1;
            if (a.type !== 'directory' && b.type === 'directory') return 1;
            return a.name.localeCompare(b.name);
        });
        const tree = buildFileTreeStructure(sorted);
        renderTreeNode(tree, fileTreeList, '');
    }

    function buildFileTreeStructure(files) {
        const tree = {};
        files.forEach(file => {
            const parts = file.path.split('/').filter(p => p);
            let current = tree;
            parts.forEach((part, index) => {
                if (!current[part]) {
                    current[part] = {
                        name: part,
                        type: index === parts.length - 1 ? file.type : 'directory',
                        path: file.path,
                        children: {}
                    };
                }
                current = current[part].children;
            });
        });
        return tree;
    }

    function renderTreeNode(node, parentElement, indent) {
        Object.keys(node).sort().forEach(key => {
            const item = node[key];
            const div = document.createElement('div');
            div.className = `file-tree-item ${item.type}`;
            div.dataset.path = item.path;
            div.style.paddingLeft = indent + 'var(--spacing-md)';

            const icon = document.createElement('span');
            icon.className = 'icon';
            icon.textContent = item.type === 'directory' ? '\uD83D\uDCC1' : getFileIcon(item.name);

            const name = document.createElement('span');
            name.textContent = item.name;
            div.appendChild(icon);
            div.appendChild(name);

            if (item.type === 'file') div.addEventListener('click', () => selectFile(div, item.path));
            parentElement.appendChild(div);

            if (item.type === 'directory' && Object.keys(item.children).length > 0) {
                renderTreeNode(item.children, parentElement, indent + '  ');
            }
        });
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const iconMap = {
            'html': '\uD83C\uDF10', 'css': '\uD83C\uDFA8', 'js': '\u26A1',
            'py': '\uD83D\uDC0D', 'json': '\uD83D\uDCCB', 'md': '\uD83D\uDCDD',
            'txt': '\uD83D\uDCC4', 'jpg': '\uD83D\uDDBC\uFE0F', 'png': '\uD83D\uDDBC\uFE0F',
            'svg': '\uD83C\uDFAD', 'xml': '\uD83D\uDCF0', 'yaml': '\u2699\uFE0F', 'yml': '\u2699\uFE0F'
        };
        return iconMap[ext] || '\uD83D\uDCC4';
    }

    function getFileExtension(filename) {
        const parts = filename.split('.');
        if (parts.length > 1) {
            const ext = parts.pop().toLowerCase();
            const langMap = {
                'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'javascript',
                'py': 'python', 'html': 'html', 'htm': 'html', 'css': 'css', 'scss': 'css',
                'json': 'json', 'xml': 'xml', 'md': 'markdown'
            };
            return langMap[ext] || ext;
        }
        return 'plaintext';
    }

    // Function to render the generated file tree for structure editor
    function renderGeneratedFileTree(structure, parentElement, isEditable) {
        parentElement.innerHTML = ''; // Clear previous content

        function buildTreeHtml(node, currentPath = '', indent = 0) {
            let html = '';
            const paddingLeft = indent * 15; // 15px per indent level

            // Render files
            (node.files || []).sort().forEach(fileName => {
                const fullPath = currentPath ? `${currentPath}/${fileName}` : fileName;
                html += `<div class="file-tree-item file" data-path="${fullPath}" style="padding-left: ${paddingLeft}px;">
                            <span class="icon">${getFileIcon(fileName)}</span>
                            <span>${escapeHtml(fileName)}</span>
                            ${isEditable ? '<button class="remove-btn" data-path="' + fullPath + '">&times;</button>' : ''}
                         </div>`;
            });

            // Render folders
            (node.folders || []).sort((a, b) => a.name.localeCompare(b.name)).forEach(folder => {
                const fullPath = currentPath ? `${currentPath}/${folder.name}` : folder.name;
                html += `<div class="file-tree-item directory" data-path="${fullPath}" style="padding-left: ${paddingLeft}px;">
                            <span class="icon">📁</span>
                            <span>${escapeHtml(folder.name)}</span>
                            ${isEditable ? '<button class="remove-btn" data-path="' + fullPath + '">&times;</button>' : ''}
                         </div>`;
                // Recursively render children
                if ((folder.folders && folder.folders.length > 0) || (folder.files && folder.files.length > 0)) {
                    html += buildTreeHtml(folder, fullPath, indent + 1);
                }
            });
            return html;
        }

        const treeHtml = buildTreeHtml(structure);
        parentElement.innerHTML = treeHtml;

        if (isEditable) {
            parentElement.querySelectorAll('.remove-btn').forEach(button => {
                button.addEventListener('click', function(event) {
                    event.stopPropagation(); // Prevent parent item click
                    const pathToRemove = this.dataset.path;
                    removePathFromStructure(pathToRemove);
                });
            });
        }
    }

    // Helper function to remove a path (file or folder) from the currentGeneratedStructure
    function removePathFromStructure(pathToRemove) {
        function removeNode(node, pathParts, index) {
            if (!node) return;

            const targetName = pathParts[index];
            const isLastPart = (index === pathParts.length - 1);

            // Check files first
            if (isLastPart && node.files) {
                const initialLength = node.files.length;
                node.files = node.files.filter(file => file !== targetName);
                if (node.files.length < initialLength) return true; // Found and removed
            }

            // Check folders
            if (node.folders) {
                for (let i = 0; i < node.folders.length; i++) {
                    if (node.folders[i].name === targetName) {
                        if (isLastPart) {
                            node.folders.splice(i, 1); // Remove the folder
                            return true;
                        } else {
                            // Recurse into the folder
                            if (removeNode(node.folders[i], pathParts, index + 1)) return true;
                        }
                    }
                }
            }
            return false;
        }

        const pathParts = pathToRemove.split('/').filter(p => p);
        if (removeNode(currentGeneratedStructure, pathParts, 0)) {
            showMessage(`Removed "${pathToRemove}" from structure.`, 'info');
            renderGeneratedFileTree(currentGeneratedStructure, generatedFileTreeContainer, true); // Re-render
        } else {
            showMessage(`Could not find "${pathToRemove}" in structure.`, 'error');
        }
    }

    // Helper function to add a path (file or folder) to the currentGeneratedStructure
    function addPathToStructure(newPath, type) {
        function addNode(node, pathParts, index) {
            if (!node) return false;

            const targetName = pathParts[index];
            const isLastPart = (index === pathParts.length - 1);

            if (isLastPart) {
                if (type === 'file') {
                    if (!node.files) node.files = [];
                    if (!node.files.includes(targetName)) {
                        node.files.push(targetName);
                        return true;
                    }
                } else { // type === 'directory'
                    if (!node.folders) node.folders = [];
                    const existingFolder = node.folders.find(f => f.name === targetName);
                    if (!existingFolder) {
                        node.folders.push({ name: targetName, folders: [], files: [] });
                        return true;
                    }
                }
                return false; // Already exists
            } else {
                if (!node.folders) node.folders = [];
                let nextNode = node.folders.find(f => f.name === targetName);
                if (!nextNode) {
                    nextNode = { name: targetName, folders: [], files: [] };
                    node.folders.push(nextNode);
                }
                return addNode(nextNode, pathParts, index + 1);
            }
        }

        const pathParts = newPath.split('/').filter(p => p);
        if (pathParts.length === 0) {
            showMessage('Invalid path provided.', 'error');
            return;
        }

        if (addNode(currentGeneratedStructure, pathParts, 0)) {
            showMessage(`Added "${newPath}" (${type}) to structure.`, 'success');
            renderGeneratedFileTree(currentGeneratedStructure, generatedFileTreeContainer, true); // Re-render
        } else {
            showMessage(`"${newPath}" (${type}) already exists or could not be added.`, 'warning');
        }
    }

    async function selectFile(element, filePathRelative, lineNumber = 0) {
        autoSaveCurrentFile(); // F10: Auto-save before switching files

        if (selectedFileElement) selectedFileElement.classList.remove('selected');
        const targetElement = element || document.querySelector(`.file-tree-item[data-path="${filePathRelative}"]`);
        if (targetElement) {
            targetElement.classList.add('selected');
            selectedFileElement = targetElement;
        }

        currentFilePath = filePathRelative;
        currentFileNameSpan.textContent = filePathRelative;
        
        // Reset dirty state for new file
        isEditorDirty = false;
        updateEditorActionButtons(); // Update button visibility based on new state and currentFilePath

        if (!monacoEditor) { // Fallback if Monaco not initialized
            monacoEditorContainer.textContent = 'Loading file content...';
        }


        try {
            const response = await fetch(`/api/projects/${currentProject}/file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path_relative: filePathRelative })
            });
            const data = await response.json();

            if (data.status === 'success') {
                currentFileContent = data.content;
                const ext = getFileExtension(filePathRelative);

                if (monacoEditor) {
                    if (monacoModel) monacoModel.dispose(); // Dispose previous model
                    monacoModel = monaco.editor.createModel(currentFileContent, ext);
                    monacoEditor.setModel(monacoModel);
                    // Clear old decorations
                    monacoDecorations = monacoEditor.deltaDecorations(monacoDecorations, []);

                    if (lineNumber > 0) {
                        monacoEditor.revealLineInCenter(lineNumber);
                        monacoEditor.setPosition({ lineNumber: lineNumber, column: 1 });
                        monacoDecorations = monacoEditor.deltaDecorations(monacoDecorations, [
                            {
                                range: new monaco.Range(lineNumber, 1, lineNumber, 1),
                                options: {
                                    isWholeLine: true,
                                    className: 'myLineDecoration',
                                    overviewRuler: {
                                        color: '#FFA726',
                                        position: monaco.editor.OverviewRulerLane.Full
                                    }
                                }
                            }
                        ]);
                    }
                } else {
                    // Fallback to pre tag if Monaco not loaded
                    monacoEditorContainer.textContent = currentFileContent;
                    monacoEditorContainer.className = `language-${ext}`;
                    // hljs.highlightElement(monacoEditorContainer); // if highlight.js is still used
                }

                if (ext === 'html' && previewTab.classList.contains('active')) updatePreview();
            } else {
                if (monacoEditor) {
                    monacoEditor.setValue(`Error: ${data.message}`);
                } else {
                    monacoEditorContainer.textContent = `Error: ${data.message}`;
                }
                currentFileContent = null;
            }
        } catch (error) {
            if (monacoEditor) {
                monacoEditor.setValue('An error occurred while reading file content.');
            } else {
                monacoEditorContainer.textContent = 'An error occurred while reading file content.';
            }
            currentFileContent = null;
        } finally {
            updateEditorActionButtons(); // Ensure buttons are correctly displayed even on load failure
        }
    }

    function navigateToCodeLocation(filePath, lineNumber = 0) {
        if (!currentProject) {
            showMessage('Please select a project first.', 'warning');
            return;
        }
        if (!filePath) {
            showMessage('No specific file to navigate to for this issue.', 'warning');
            return;
        }

        // Switch to code tab
        document.querySelector('.tab-btn[data-tab="code"]').click();

        // Find the file in the file tree and select it, then load content
        // The selectFile function already handles loading into Monaco and positioning
        selectFile(null, filePath, lineNumber);
    }

    function updatePreview() {
        if (!currentFilePath || !currentFileContent) {
            previewFrame.srcdoc = '<body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;color:#666;">Select an HTML file to preview</body>';
            return;
        }
        const ext = getFileExtension(currentFilePath);
        if (ext === 'html') {
            previewFrame.srcdoc = currentFileContent;
        } else {
            previewFrame.srcdoc = `<body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;color:#666;text-align:center;">
                <div><div style="font-size:48px;margin-bottom:16px;">\uD83D\uDCC4</div>
                <div>Preview not available for .${ext} files</div>
                <div style="margin-top:8px;opacity:0.6;font-size:14px;">Switch to Code tab to view content</div></div></body>`;
        }
    }

    // ==================== Benchmark ====================
    benchFetchModels.addEventListener('click', async function() {
        const url = benchOllamaUrl.value.trim();
        const params = url ? `?url=${encodeURIComponent(url)}` : '';
        benchModelList.innerHTML = '<div class="model-list-empty">Loading models...</div>';

        try {
            const resp = await fetch(`/api/benchmark/models${params}`);
            const data = await resp.json();

            if (data.status !== 'ok') {
                benchModelList.innerHTML = `<div class="model-list-empty" style="color:var(--color-error);">${escapeHtml(data.message)}</div>`;
                return;
            }

            if (!benchOllamaUrl.value.trim()) benchOllamaUrl.value = data.ollama_url;

            if (data.models.length === 0) {
                benchModelList.innerHTML = '<div class="model-list-empty">No models found on this server</div>';
                return;
            }

            benchModelList.innerHTML = '';
            data.models.forEach(m => {
                const label = document.createElement('label');
                label.className = 'model-item';
                label.innerHTML = `
                    <input type="checkbox" value="${escapeHtml(m.name)}">
                    <span class="model-item-name">${escapeHtml(m.name)}</span>
                    <span class="model-item-size">${escapeHtml(m.size_human)}</span>
                `;
                label.querySelector('input').addEventListener('change', updateBenchStartBtn);
                benchModelList.appendChild(label);
            });
        } catch (err) {
            benchModelList.innerHTML = `<div class="model-list-empty" style="color:var(--color-error);">Connection error: ${escapeHtml(err.message)}</div>`;
        }
    });

    function updateBenchStartBtn() {
        const checked = benchModelList.querySelectorAll('input[type="checkbox"]:checked');
        benchStartBtn.disabled = checked.length === 0;
    }

    benchStartBtn.addEventListener('click', async function() {
        const checked = benchModelList.querySelectorAll('input[type="checkbox"]:checked');
        const models = Array.from(checked).map(cb => cb.value);
        if (models.length === 0) return;

        benchStartBtn.disabled = true;
        benchOutput.innerHTML = '<div class="bench-progress"><p>Starting benchmark...</p></div>';

        try {
            const resp = await fetch('/api/benchmark/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    models: models,
                    ollama_url: benchOllamaUrl.value.trim()
                })
            });
            const data = await resp.json();

            if (data.status !== 'started') {
                benchOutput.innerHTML = `<div class="bench-progress" style="color:var(--color-error);">${escapeHtml(data.message)}</div>`;
                benchStartBtn.disabled = false;
                return;
            }

            // Open SSE stream
            if (benchEventSource) benchEventSource.close();
            benchEventSource = new EventSource(`/api/benchmark/stream`);

            benchEventSource.onmessage = function(event) {
                let parsed;
                try { parsed = JSON.parse(event.data); } catch { return; }

                switch (parsed.type) {
                    case 'model_start':
                        appendBenchLog(`[${parsed.index}/${parsed.total}] Testing model: ${parsed.model}...`);
                        break;

                    case 'model_done':
                        appendBenchLog(`[${parsed.index}/${parsed.total}] ${parsed.model} done.`, 'success');
                        if (parsed.result) appendBenchResult(parsed.result);
                        break;

                    case 'benchmark_done':
                        appendBenchLog('Benchmark completed!', 'success');
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        loadBenchHistory();
                        break;

                    case 'error':
                        appendBenchLog(`Error: ${parsed.message}`, 'error');
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        break;

                    case 'stream_end':
                        benchEventSource.close();
                        benchEventSource = null;
                        benchStartBtn.disabled = false;
                        break;
                }
            };

            benchEventSource.onerror = function() {
                benchEventSource.close();
                benchEventSource = null;
                benchStartBtn.disabled = false;
            };

        } catch (err) {
            benchOutput.innerHTML = `<div class="bench-progress" style="color:var(--color-error);">Connection error: ${escapeHtml(err.message)}</div>`;
            benchStartBtn.disabled = false;
        }
    });

    function appendBenchLog(msg, type = 'info') {
        const placeholder = benchOutput.querySelector('.bench-placeholder');
        if (placeholder) placeholder.remove();
        const progress = benchOutput.querySelector('.bench-progress');
        if (progress) progress.remove();

        const line = document.createElement('div');
        line.className = `bench-log-line ${type}`;
        const ts = new Date().toLocaleTimeString();
        line.innerHTML = `<span style="opacity:0.5">[${ts}]</span> ${escapeHtml(msg)}`;
        benchOutput.appendChild(line);
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    function appendBenchResult(result) {
        const card = document.createElement('div');
        card.className = 'bench-result-card';

        const successCount = result.projects_results
            ? result.projects_results.filter(p => p.status === 'Success').length
            : 0;
        const totalTasks = result.projects_results ? result.projects_results.length : 0;
        const dur = result.duration_sec ? `${Math.floor(result.duration_sec / 60)}m ${Math.floor(result.duration_sec % 60)}s` : '-';

        card.innerHTML = `
            <div class="bench-result-header">
                <strong>${escapeHtml(result.model)}</strong>
                <span class="bench-result-size">${escapeHtml(result.model_size_human || '')}</span>
            </div>
            <div class="bench-result-stats">
                <div class="bench-stat">
                    <span class="bench-stat-value">${successCount}/${totalTasks}</span>
                    <span class="bench-stat-label">Tasks OK</span>
                </div>
                <div class="bench-stat">
                    <span class="bench-stat-value">${dur}</span>
                    <span class="bench-stat-label">Duration</span>
                </div>
                <div class="bench-stat">
                    <span class="bench-stat-value">${result.tokens_per_second || 0}</span>
                    <span class="bench-stat-label">tok/s</span>
                </div>
            </div>
        `;
        benchOutput.appendChild(card);
        benchOutput.scrollTop = benchOutput.scrollHeight;
    }

    async function loadBenchHistory() {
        try {
            const resp = await fetch('/api/benchmark/results');
            const data = await resp.json();
            benchHistoryList.innerHTML = '';

            if (data.status === 'ok' && data.results.length > 0) {
                data.results.slice(0, 10).forEach(r => {
                    const item = document.createElement('button');
                    item.className = 'bench-history-item';
                    const date = new Date(r.modified * 1000).toLocaleString();
                    item.innerHTML = `<span>${escapeHtml(r.filename)}</span><span class="bench-history-date">${date}</span>`;
                    item.addEventListener('click', () => loadBenchResult(r.filename));
                    benchHistoryList.appendChild(item);
                });
            } else {
                benchHistoryList.innerHTML = '<div class="model-list-empty">No past results found</div>';
            }
        } catch (err) {
            benchHistoryList.innerHTML = '<div class="model-list-empty">Error loading results</div>';
        }
    }

    async function loadBenchResult(filename) {
        try {
            const resp = await fetch(`/api/benchmark/results/${encodeURIComponent(filename)}`);
            const data = await resp.json();
            if (data.status !== 'ok') return;

            benchOutput.innerHTML = '';
            appendBenchLog(`Loaded: ${filename}`);
            data.data.forEach(result => appendBenchResult(result));
        } catch (err) {
            console.error('Error loading bench result:', err);
        }
    }

    // ==================== Refresh Files ====================
    const refreshFilesBtn = document.getElementById('refresh-files');
    if (refreshFilesBtn) {
        refreshFilesBtn.addEventListener('click', function() {
            if (currentProject) fetchFileTree(currentProject);
        });
    }

    // ==================== Status Check ====================
    async function checkOllamaStatus() {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-indicator span');
        if (!statusDot || !statusText) return;

        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            if (data.status === 'ok') {
                statusDot.style.background = 'var(--color-success)';
                statusText.textContent = 'Ollama connected';
            } else {
                statusDot.style.background = 'var(--color-error)';
                statusText.textContent = 'Ollama offline';
            }
        } catch {
            statusDot.style.background = 'var(--color-error)';
            statusText.textContent = 'Ollama offline';
        }
    }

    // ==================== Theme Toggle ====================
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const themeLabel = document.getElementById('theme-label');

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ollash-theme', theme);
        if (monacoEditor) {
            monaco.editor.setTheme(theme === 'dark' ? 'vs-dark' : 'vs-light');
        }
    }

    if (themeToggle) {
        const savedTheme = localStorage.getItem('ollash-theme') || 'dark';
        setTheme(savedTheme);
        themeToggle.addEventListener('click', function () {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // Initialize Monaco Editor
    if (monacoEditorContainer) {
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.29.1/min/vs' }});
        require(['vs/editor/editor.main'], function() {
            monacoEditor = monaco.editor.create(monacoEditorContainer, {
                value: '// Select a file to view its content',
                language: 'plaintext',
                theme: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light',
                automaticLayout: true,
                readOnly: false,
                minimap: { enabled: false }
            });

            // Initial update of editor action buttons
            updateEditorActionButtons(); // Hide buttons initially when no file is open

            // Update theme if it changes
            new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.attributeName === 'data-theme') {
                        monaco.editor.setTheme((document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light');
                    }
                });
            }).observe(document.documentElement, { attributes: true });

            // Add listener to update dirty state when content changes
            monacoEditor.onDidChangeModelContent(() => {
                isEditorDirty = true;
                updateEditorActionButtons();
            });
        });
    }


    // Add event listener for the Save button
    saveFileBtn.addEventListener('click', async function() {
        if (!currentProject || !currentFilePath || !monacoEditor || !isEditorDirty) {
            showMessage('No active project, file, or unsaved changes to save.', 'warning');
            return;
        }

        showMessage('Saving file...', 'info');
        saveFileBtn.disabled = true;

        try {
            const contentToSave = monacoEditor.getValue();
            const response = await fetch(`/api/projects/${currentProject}/save_file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path_relative: currentFilePath,
                    content: contentToSave
                })
            });
            const data = await response.json();

            if (data.status === 'success') {
                isEditorDirty = false;
                updateEditorActionButtons();
                showMessage('File saved successfully!', 'success');
            } else {
                showMessage(`Error saving file: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('Error saving file:', error);
            showMessage('An error occurred while trying to save the file.', 'error');
        } finally {
            saveFileBtn.disabled = false;
        }
    });


    // ==================== Project Export ====================
    const exportBtn = document.getElementById('export-project-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            if (currentProject) {
                window.location.href = `/api/projects/${encodeURIComponent(currentProject)}/export`;
            }
        });
    }
    // Show/hide export button when project is selected
    const projectSelect = document.getElementById('existing-projects');
    if (projectSelect && exportBtn) {
        projectSelect.addEventListener('change', function () {
            exportBtn.style.display = this.value ? 'inline-flex' : 'none';
        });
    }

    // ==================== Clone Project ====================
    const cloneBtn = document.getElementById('clone-project-btn');
    if (cloneBtn) {
        cloneBtn.addEventListener('click', function () {
            const gitUrl = prompt('Enter the Git repository URL to clone:');
            if (!gitUrl) return;

            const projectName = prompt('Project name (leave empty to infer from URL):', '');

            const formData = new FormData();
            formData.append('git_url', gitUrl);
            if (projectName) formData.append('project_name', projectName);

            cloneBtn.disabled = true;
            cloneBtn.textContent = 'Cloning...';

            fetch('/api/projects/clone', { method: 'POST', body: formData })
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (data.status === 'success') {
                        alert('Project "' + data.project_name + '" cloned successfully!');
                        // Refresh project list
                        if (typeof loadProjectList === 'function') loadProjectList();
                        var sel = document.getElementById('existing-projects');
                        if (sel) {
                            // Trigger change after list refresh
                            setTimeout(function () {
                                sel.value = data.project_name;
                                sel.dispatchEvent(new Event('change'));
                            }, 1000);
                        }
                    } else {
                        alert('Clone failed: ' + data.message);
                    }
                })
                .catch(function (err) { alert('Clone error: ' + err.message); })
                .finally(function () {
                    cloneBtn.disabled = false;
                    cloneBtn.textContent = 'Clone from Git';
                });
        });
    }

    // ==================== Chat Persistence (localStorage) ====================
    function saveChatHistory() {
        const messages = document.getElementById('chat-messages');
        if (!messages) return;
        const bubbles = messages.querySelectorAll('.chat-message');
        const history = [];
        bubbles.forEach(function (el) {
            const isUser = el.classList.contains('user');
            const bubble = el.querySelector('.chat-bubble');
            if (bubble) {
                history.push({ role: isUser ? 'user' : 'assistant', html: bubble.innerHTML });
            }
        });
        if (history.length > 0) {
            localStorage.setItem('ollash-chat-history', JSON.stringify(history));
        }
    }

    function restoreChatHistory() {
        const saved = localStorage.getItem('ollash-chat-history');
        if (!saved) return;
        try {
            const history = JSON.parse(saved);
            if (!history.length) return;
            const messages = document.getElementById('chat-messages');
            if (!messages) return;
            // Remove the welcome screen
            const welcome = messages.querySelector('.chat-welcome');
            if (welcome) welcome.remove();
            history.forEach(function (entry) {
                const msgDiv = document.createElement('div');
                msgDiv.className = `chat-message ${entry.role === 'user' ? 'user' : 'assistant'}`;
                const bubble = document.createElement('div');
                bubble.className = 'chat-bubble';
                bubble.innerHTML = entry.html;
                msgDiv.appendChild(bubble);
                messages.appendChild(msgDiv);
            });
            messages.scrollTop = messages.scrollHeight;
        } catch {
            // Corrupted data, ignore
        }
    }

    // Save chat after each SSE stream ends
    const origPushFinal = window._ollashSaveChatHook;
    window._ollashSaveChatHook = saveChatHistory;

    // ==================== F10: Monaco Autosave ====================
    async function autoSaveCurrentFile() {
        if (!currentProject || !currentFilePath || !monacoEditor || !isEditorDirty) return;
        try {
            const contentToSave = monacoEditor.getValue();
            const response = await fetch(`/api/projects/${currentProject}/save_file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path_relative: currentFilePath, content: contentToSave })
            });
            const data = await response.json();
            if (data.status === 'success') {
                isEditorDirty = false;
                updateEditorActionButtons();
                notificationService.info('Auto-saved', 2000);
            }
        } catch (err) {
            console.error('Auto-save failed:', err);
        }
    }

    // ==================== F11: Log Filtering ====================
    logFilterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            logFilterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeLogFilter = this.dataset.filter;

            const logLines = agentLogs.querySelectorAll('.log-line');
            logLines.forEach(line => {
                if (activeLogFilter === 'all') {
                    line.classList.remove('filtered-out');
                } else {
                    const logType = line.dataset.logType || 'info';
                    if (logType === activeLogFilter) {
                        line.classList.remove('filtered-out');
                    } else {
                        line.classList.add('filtered-out');
                    }
                }
            });
        });
    });

    // ==================== F2: Wizard Mode ====================
    function wizardGoTo(step) {
        currentWizardStep = step;
        wizardSteps.forEach(s => s.classList.remove('active'));
        wizardIndicators.forEach((ind, i) => {
            ind.classList.remove('active', 'completed');
            if (i + 1 < step) ind.classList.add('completed');
            else if (i + 1 === step) ind.classList.add('active');
        });
        const target = document.getElementById(`wizard-step-${step}`);
        if (target) target.classList.add('active');
    }

    wizardNextBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const nextStep = currentWizardStep + 1;
            // Validate current step
            if (currentWizardStep === 1) {
                const name = document.getElementById('project-name');
                if (name && !name.value.trim()) {
                    showMessage('Please enter a project name.', 'error');
                    return;
                }
            }
            if (nextStep <= 3) wizardGoTo(nextStep);
        });
    });

    wizardBackBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            if (currentWizardStep > 1) wizardGoTo(currentWizardStep - 1);
        });
    });

    if (wizardGenerateBtn) {
        wizardGenerateBtn.addEventListener('click', function() {
            const desc = document.getElementById('project-description');
            if (desc && !desc.value.trim()) {
                showMessage('Please enter a project description.', 'error');
                return;
            }
            handleGenerateStructureSubmit(null);
        });
    }

    // ==================== F6: Floating Terminal ====================
    function toggleFloatingTerminal() {
        if (!floatingTerminal) return;
        if (floatingTerminalState === 'hidden') {
            floatingTerminal.classList.add('visible');
            floatingTerminal.classList.remove('minimized', 'maximized');
            floatingTerminalState = 'normal';
            initTerminalIfNeeded();
        } else {
            floatingTerminal.classList.remove('visible', 'minimized', 'maximized');
            floatingTerminalState = 'hidden';
        }
    }

    function initTerminalIfNeeded() {
        if (term) {
            setTimeout(() => { fitAddon.fit(); term.focus(); }, 100);
            return;
        }
        if (typeof Terminal === 'undefined') return;
        term = new Terminal({
            cursorBlink: true,
            theme: { background: '#000000', foreground: '#F8F8F8' },
            fontFamily: 'JetBrains Mono, Fira Code, monospace',
            fontSize: 14
        });
        fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        term.open(terminalContainer);
        fitAddon.fit();
        term.writeln('\x1b[1;32mOllash Terminal\x1b[0m');
        term.writeln('Type commands and press Enter.');
        term.write(prompt);

        term.onData(data => {
            if (data === '\r') {
                term.writeln('');
                if (currentCommand.trim()) executeTerminalCommand(currentCommand.trim());
                currentCommand = '';
                term.write(prompt);
            } else if (data === '\x7f') {
                if (currentCommand.length > 0) {
                    currentCommand = currentCommand.slice(0, -1);
                    term.write('\b \b');
                }
            } else {
                currentCommand += data;
                term.write(data);
            }
        });
    }

    async function executeTerminalCommand(cmd) {
        if (!currentProject) {
            term.writeln('\x1b[31mNo project selected.\x1b[0m');
            return;
        }
        try {
            const resp = await fetch('/api/terminal/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd, project_name: currentProject })
            });
            const data = await resp.json();
            if (data.output) term.writeln(data.output);
            if (data.error) term.writeln(`\x1b[31m${data.error}\x1b[0m`);
        } catch (err) {
            term.writeln(`\x1b[31mError: ${err.message}\x1b[0m`);
        }
    }

    if (toggleTerminalBtn) {
        toggleTerminalBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleFloatingTerminal();
        });
    }
    if (terminalMinimizeBtn) {
        terminalMinimizeBtn.addEventListener('click', function() {
            if (!floatingTerminal) return;
            floatingTerminal.classList.toggle('minimized');
            floatingTerminal.classList.remove('maximized');
            floatingTerminalState = floatingTerminal.classList.contains('minimized') ? 'minimized' : 'normal';
        });
    }
    if (terminalMaximizeBtn) {
        terminalMaximizeBtn.addEventListener('click', function() {
            if (!floatingTerminal) return;
            floatingTerminal.classList.toggle('maximized');
            floatingTerminal.classList.remove('minimized');
            floatingTerminalState = floatingTerminal.classList.contains('maximized') ? 'maximized' : 'normal';
            if (term && fitAddon) setTimeout(() => fitAddon.fit(), 100);
        });
    }
    if (terminalCloseBtn) {
        terminalCloseBtn.addEventListener('click', function() {
            if (!floatingTerminal) return;
            floatingTerminal.classList.remove('visible', 'minimized', 'maximized');
            floatingTerminalState = 'hidden';
        });
    }

    // Floating terminal header drag to resize
    if (floatingTerminalHeader) {
        let isResizing = false;
        let startY, startHeight;
        floatingTerminalHeader.addEventListener('mousedown', function(e) {
            if (e.target.closest('button')) return;
            isResizing = true;
            startY = e.clientY;
            startHeight = floatingTerminal.offsetHeight;
            document.body.style.userSelect = 'none';
        });
        document.addEventListener('mousemove', function(e) {
            if (!isResizing) return;
            const delta = startY - e.clientY;
            const newHeight = Math.max(60, Math.min(window.innerHeight * 0.7, startHeight + delta));
            floatingTerminal.style.height = newHeight + 'px';
        });
        document.addEventListener('mouseup', function() {
            if (isResizing) {
                isResizing = false;
                document.body.style.userSelect = '';
                if (term && fitAddon) fitAddon.fit();
            }
        });
    }

    // ==================== F4: System Health Dashboard ====================
    async function fetchSystemHealth() {
        try {
            const resp = await fetch('/api/system/health');
            const data = await resp.json();
            if (data.status !== 'ok') return;

            const cpu = data.cpu_percent || 0;
            const ram = data.ram_percent || 0;

            if (healthCpuBar) {
                healthCpuBar.style.width = cpu + '%';
                healthCpuBar.className = 'health-bar-fill ' + getHealthColor(cpu);
            }
            if (healthCpuVal) healthCpuVal.textContent = Math.round(cpu) + '%';

            if (healthRamBar) {
                healthRamBar.style.width = ram + '%';
                healthRamBar.className = 'health-bar-fill ' + getHealthColor(ram);
            }
            if (healthRamVal) healthRamVal.textContent = Math.round(ram) + '%';

            if (data.gpu && data.gpu.util_percent !== undefined) {
                const gpu = data.gpu.util_percent;
                if (healthGpuMetric) healthGpuMetric.style.display = 'flex';
                if (healthGpuBar) {
                    healthGpuBar.style.width = gpu + '%';
                    healthGpuBar.className = 'health-bar-fill ' + getHealthColor(gpu);
                }
                if (healthGpuVal) healthGpuVal.textContent = Math.round(gpu) + '%';
            } else {
                if (healthGpuMetric) healthGpuMetric.style.display = 'none';
            }
        } catch {
            // Silently fail - health dashboard is optional
        }
    }

    function getHealthColor(percent) {
        if (percent < 60) return 'green';
        if (percent < 85) return 'yellow';
        return 'red';
    }

    // ==================== F5: Project Mini-map (Dependency Graph) ====================
    async function loadProjectMinimap() {
        if (!currentProject || !minimapContainer) return;
        minimapContainer.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-text-muted)">Loading dependency graph...</div>';

        try {
            const resp = await fetch(`/api/projects/${encodeURIComponent(currentProject)}/dependency-graph`);
            const data = await resp.json();
            if (data.status !== 'ok') {
                minimapContainer.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--color-text-muted)">${escapeHtml(data.message || 'No graph data')}</div>`;
                return;
            }

            if (data.nodes.length === 0) {
                minimapContainer.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--color-text-muted)">No files found in project</div>';
                return;
            }

            minimapContainer.innerHTML = '';

            const nodes = new vis.DataSet(data.nodes);
            const edges = new vis.DataSet(data.edges);

            if (minimapNetwork) minimapNetwork.destroy();
            minimapNetwork = new vis.Network(minimapContainer, { nodes, edges }, {
                physics: {
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: { gravitationalConstant: -30, centralGravity: 0.005, springLength: 100, springConstant: 0.02 },
                    stabilization: { iterations: 100 }
                },
                nodes: {
                    shape: 'dot',
                    size: 12,
                    font: { size: 11, color: '#e4e4e7' },
                    borderWidth: 2
                },
                edges: {
                    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                    color: { color: '#2a2a35', highlight: '#6366f1' },
                    width: 1
                },
                interaction: { hover: true, tooltipDelay: 200 }
            });

            // Click node -> navigate to file
            minimapNetwork.on('click', function(params) {
                if (params.nodes.length > 0) {
                    const filePath = params.nodes[0];
                    document.querySelector('.tab-btn[data-tab="code"]').click();
                    selectFile(null, filePath);
                }
            });
        } catch (err) {
            minimapContainer.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--color-error)">Error loading graph: ${escapeHtml(err.message)}</div>`;
        }
    }

    // ==================== F7: Diff Modal ====================
    async function showDiffModal(filepath, modifiedContent) {
        if (!diffModal || !diffEditorContainer) return;

        diffCurrentFilePath = filepath;
        diffModifiedContent = modifiedContent;

        // Load original content
        if (currentProject) {
            try {
                const resp = await fetch(`/api/projects/${currentProject}/file`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_path_relative: filepath })
                });
                const data = await resp.json();
                diffOriginalContent = data.status === 'success' ? data.content : '';
            } catch {
                diffOriginalContent = '';
            }
        }

        if (diffFilePath) diffFilePath.textContent = filepath;
        diffModal.style.display = 'flex';

        // Create diff editor if Monaco is loaded
        if (typeof monaco !== 'undefined') {
            diffEditorContainer.innerHTML = '';
            const ext = getFileExtension(filepath);
            diffEditor = monaco.editor.createDiffEditor(diffEditorContainer, {
                automaticLayout: true,
                readOnly: false,
                theme: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light',
                renderSideBySide: true
            });
            diffEditor.setModel({
                original: monaco.editor.createModel(diffOriginalContent, ext),
                modified: monaco.editor.createModel(diffModifiedContent, ext)
            });
        }
    }

    function closeDiffModal() {
        if (diffModal) diffModal.style.display = 'none';
        if (diffEditor) {
            diffEditor.dispose();
            diffEditor = null;
        }
    }

    if (diffApplyBtn) {
        diffApplyBtn.addEventListener('click', async function() {
            if (!currentProject || !diffCurrentFilePath || !diffEditor) return;
            const modified = diffEditor.getModel().modified.getValue();
            try {
                const resp = await fetch('/api/refactor/apply', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_name: currentProject,
                        file_path: diffCurrentFilePath,
                        modified_content: modified
                    })
                });
                const data = await resp.json();
                if (data.status === 'ok') {
                    notificationService.success('Changes applied successfully!');
                    closeDiffModal();
                    // Reload file if it's currently open
                    if (currentFilePath === diffCurrentFilePath) {
                        selectFile(null, currentFilePath);
                    }
                } else {
                    notificationService.error(data.message || 'Failed to apply changes.');
                }
            } catch (err) {
                notificationService.error('Error applying changes: ' + err.message);
            }
        });
    }

    if (diffDiscardBtn) {
        diffDiscardBtn.addEventListener('click', closeDiffModal);
    }

    // Close diff modal on background click
    if (diffModal) {
        diffModal.addEventListener('click', function(e) {
            if (e.target === diffModal) closeDiffModal();
        });
    }

    // ==================== F8: Smart Prompt Library ====================
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

    function renderPromptLibrary(filter = 'all') {
        const grid = document.getElementById('prompt-library-grid');
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
            card.addEventListener('click', function() {
                chatInput.value = p.prompt;
                chatInput.style.height = 'auto';
                chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
                // Set agent type
                selectedAgentType = p.agent;
                document.querySelectorAll('.agent-card').forEach(c => {
                    c.classList.toggle('selected', c.dataset.agent === p.agent);
                });
                // Close prompt library
                if (promptLibraryPanel) promptLibraryPanel.classList.remove('visible');
                chatInput.focus();
            });
            grid.appendChild(card);
        });
    }

    if (promptLibraryToggle) {
        promptLibraryToggle.addEventListener('click', function() {
            if (!promptLibraryPanel) return;
            promptLibraryPanel.classList.toggle('visible');
            if (promptLibraryPanel.classList.contains('visible')) {
                renderPromptLibrary();
            }
        });
    }

    promptCatBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            promptCatBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            renderPromptLibrary(this.dataset.category);
        });
    });

    // ==================== Init ====================
    restoreChatHistory();
    populateExistingProjects();
    checkOllamaStatus();
    setInterval(checkOllamaStatus, 30000);

    // F9: Request desktop notification permission
    notificationService.requestDesktopPermission();

    // F4: Start health dashboard polling
    fetchSystemHealth();
    setInterval(fetchSystemHealth, 10000);

    // F2: Initialize wizard to step 1
    wizardGoTo(1);

    // ==================== Automations View ==================== 
    const newAutomationBtn = document.getElementById('new-automation-btn');
    const automationModal = document.getElementById('automation-modal');
    const automationForm = document.getElementById('automation-form');
    const automationsGrid = document.getElementById('automations-grid');
    const taskScheduleSelect = document.getElementById('task-schedule');
    const cronGroup = document.getElementById('cron-group');

    // Add Path functionality
    if (addPathBtn && addPathInput) {
        addPathBtn.addEventListener('click', function() {
            const path = addPathInput.value.trim();
            if (!path) {
                showMessage('Path cannot be empty.', 'error');
                return;
            }

            // Determine if it's a file or folder based on presence of extension
            const isFile = path.includes('.') && path.split('/').pop().includes('.');
            const type = isFile ? 'file' : 'directory';

            addPathToStructure(path, type);
            addPathInput.value = ''; // Clear input
        });
    }

    if (newAutomationBtn) {
        newAutomationBtn.addEventListener('click', () => {
            automationModal.style.display = 'flex';
        });
    }

    if (taskScheduleSelect) {
        taskScheduleSelect.addEventListener('change', (e) => {
            handleScheduleChange(e.target.value);
        });
    }

    if (automationForm) {
        automationForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveNewAutomation();
        });
    }

    // Load automations when view is clicked
    const navItems2 = document.querySelectorAll('[data-view="automations"]');
    navItems2.forEach(item => {
        item.addEventListener('click', loadAutomations);
    });

    // Load automations on page load
    loadAutomations();
});

// Monaco Editor related global functions and styling
// This CSS is for the line highlighting in Monaco Editor
const style = document.createElement('style');
style.textContent = `
.myLineDecoration {
    background: #ff000030; /* Light red background */
    border: 1px solid #ff0000;
}
`;
document.head.appendChild(style);

/**
 * Close automation modal
 */
function closeAutomationModal() {
    const modal = document.getElementById('automation-modal');
    if (modal) {
        modal.style.display = 'none';
        // Reset form
        const form = document.getElementById('automation-form');
        if (form) form.reset();
    }
}

/**
 * Handle schedule type change
 */
function handleScheduleChange(value) {
    const cronGroup = document.getElementById('cron-group');
    if (cronGroup) {
        cronGroup.style.display = value === 'custom' ? 'block' : 'none';
    }
}

/**
 * Save new automation task
 */
async function saveNewAutomation() {
    const taskName = document.getElementById('task-name').value;
    const taskAgent = document.getElementById('task-agent').value;
    const taskPrompt = document.getElementById('task-prompt').value;
    const taskSchedule = document.getElementById('task-schedule').value;
    const taskCron = document.getElementById('task-cron').value;
    const taskNotifyEmail = document.getElementById('task-notify-email').checked;

    if (!taskName || !taskAgent || !taskPrompt) {
        notificationService.error('Please fill in all required fields');
        return;
    }

    const taskData = {
        name: taskName,
        agent: taskAgent,
        prompt: taskPrompt,
        schedule: taskSchedule,
        cron: taskSchedule === 'custom' ? taskCron : null,
        notifyEmail: taskNotifyEmail
    };

    try {
        const response = await fetch('/api/automations', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': localStorage.getItem('ollash-api-key') || ''
            },
            body: JSON.stringify(taskData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        notificationService.success(`Task "${taskName}" created successfully!`);
        closeAutomationModal();
        await loadAutomations();
    } catch (error) {
        notificationService.error(`Error creating task: ${error.message}`);
        console.error('Error:', error);
    }
}

/**
 * Load and display all automations
 */
async function loadAutomations() {
    try {
        const response = await fetch('/api/automations', {
            headers: {
                'Authorization': localStorage.getItem('ollash-api-key') || ''
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const tasks = await response.json();
        const grid = document.getElementById('automations-grid');
        
        if (!grid) return;

        if (tasks.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: var(--spacing-xl); color: var(--color-text-muted);">
                    <p>No automations yet. Create one to get started!</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = tasks.map(task => `
            <div class="automation-card">
                <div class="automation-card-header">
                    <h3>${escapeHtml(task.name)}</h3>
                    <span class="automation-status ${task.status}">
                        ${task.status === 'active' ? '● Active' : '○ Inactive'}
                    </span>
                </div>
                <div class="automation-card-meta">
                    <div class="automation-card-meta-item">
                        <span class="automation-card-meta-label">Agent:</span>
                        <span class="automation-card-meta-value">${escapeHtml(task.agent)}</span>
                    </div>
                    <div class="automation-card-meta-item">
                        <span class="automation-card-meta-label">Schedule:</span>
                        <span class="automation-card-meta-value">${escapeHtml(task.schedule)}</span>
                    </div>
                    ${task.lastRun ? `<div class="automation-card-meta-item">
                        <span class="automation-card-meta-label">Last run:</span>
                        <span class="automation-card-meta-value">${new Date(task.lastRun).toLocaleString()}</span>
                    </div>` : ''}
                    ${task.nextRun ? `<div class="automation-card-meta-item">
                        <span class="automation-card-meta-label">Next run:</span>
                        <span class="automation-card-meta-value">${new Date(task.nextRun).toLocaleString()}</span>
                    </div>` : ''}
                </div>
                <div class="automation-card-actions">
                    <button onclick="runAutomationNow('${task.id}')" class="btn-secondary">Run Now</button>
                    <button onclick="toggleAutomation('${task.id}')" class="btn-secondary">
                        ${task.status === 'active' ? 'Disable' : 'Enable'}
                    </button>
                    <button onclick="deleteAutomation('${task.id}')" class="btn-secondary" style="color: var(--color-error);">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading automations:', error);
        notificationService.error(`Failed to load automations: ${error.message}`);
    }
}

/**
 * Toggle automation active/inactive
 */
async function toggleAutomation(taskId) {
    try {
        const response = await fetch(`/api/automations/${taskId}/toggle`, {
            method: 'PUT',
            headers: {
                'Authorization': localStorage.getItem('ollash-api-key') || ''
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        notificationService.success(result.message || 'Task updated');
        await loadAutomations();
    } catch (error) {
        notificationService.error(`Error toggling automation: ${error.message}`);
    }
}

/**
 * Run automation immediately
 */
async function runAutomationNow(taskId) {
    try {
        const response = await fetch(`/api/automations/${taskId}/run`, {
            method: 'POST',
            headers: {
                'Authorization': localStorage.getItem('ollash-api-key') || ''
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        notificationService.success(result.message || 'Task started');
    } catch (error) {
        notificationService.error(`Error running automation: ${error.message}`);
    }
}

/**
 * Delete automation
 */
async function deleteAutomation(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }

    try {
        const response = await fetch(`/api/automations/${taskId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': localStorage.getItem('ollash-api-key') || ''
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        notificationService.success('Task deleted successfully');
        await loadAutomations();
    } catch (error) {
        notificationService.error(`Error deleting automation: ${error.message}`);
    }
}
