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
            tabBtns.forEach(tab => tab.classList.remove('active'));
            this.classList.add('active');
            if (tabId === 'preview') {
                previewTab.classList.add('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.remove('active');
                terminalTabContent.classList.remove('active');
                updatePreview();
            } else if (tabId === 'code') {
                previewTab.classList.remove('active');
                codeTab.classList.add('active');
                issuesTabContent.classList.remove('active');
                terminalTabContent.classList.remove('active');
                // Ensure editor is laid out correctly when tab is shown
                if (monacoEditor) monacoEditor.layout();
            } else if (tabId === 'issues') {
                previewTab.classList.remove('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.add('active');
                terminalTabContent.classList.remove('active');
                loadProjectIssues(currentProject);
            } else if (tabId === 'terminal') {
                previewTab.classList.remove('active');
                codeTab.classList.remove('active');
                issuesTabContent.classList.remove('active');
                terminalTabContent.classList.add('active');
                if (term) {
                    fitAddon.fit();
                    term.focus();
                }
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
        const timestamp = new Date().toLocaleTimeString();
        logLine.innerHTML = `<span style="opacity: 0.5">[${timestamp}]</span> ${escapeHtml(message)}`;
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
        return escapeHtml(text)
            .replace(/```([\s\S]*?)```/g, '<pre class="chat-code-block">$1</pre>')
            .replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>')
            .replace(/\n/g, '<br>');
    }

    sendBtn.addEventListener('click', sendChatMessage);

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
        event.preventDefault();

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

                // Hide creation form, show structure editor
                createProjectFormContainer.style.display = 'none';
                generatedStructureSection.style.display = 'block';

                renderGeneratedFileTree(currentGeneratedStructure, generatedFileTreeContainer, true);

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
                createProjectFormContainer.style.display = 'block'; // Show the initial form again
                generatedStructureSection.style.display = 'none'; // Hide structure editor
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
                    // Mark final phase as completed
                    updatePhaseTimeline(8, 'completed'); // Assuming 8 phases for completion
                    break;
                case 'error':
                    addLogLine(`ERROR: ${parsedEvent.message}`, 'error');
                    // Mark current phase as error, and potentially all subsequent as error or cancelled
                    updatePhaseTimeline(parsedEvent.phase, 'error');
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

    // ==================== Init ====================
    restoreChatHistory();
    populateExistingProjects();
    checkOllamaStatus();
    setInterval(checkOllamaStatus, 30000);

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
