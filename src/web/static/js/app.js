document.addEventListener('DOMContentLoaded', function() {
    // ==================== DOM Elements ====================
    // Projects
    const createProjectForm = document.getElementById('create-project-form');
    const statusMessage = document.getElementById('status-message');
    const existingProjectsSelect = document.getElementById('existing-projects');
    const fileTreeList = document.getElementById('file-tree-list');
    const fileCodeDisplay = document.getElementById('file-code-display');
    const currentFileNameSpan = document.getElementById('current-file-name');
    const agentLogs = document.getElementById('agent-logs');
    const projectWorkspace = document.getElementById('project-workspace');
    const previewFrame = document.getElementById('preview-frame');
    const clearLogsBtn = document.getElementById('clear-logs');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const previewTab = document.getElementById('preview-tab');
    const codeTab = document.getElementById('code-tab');

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
                updatePreview();
            } else {
                previewTab.classList.remove('active');
                codeTab.classList.add('active');
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

    async function sendChatMessage() {
        const message = chatInput.value.trim();
        if (!message || isChatBusy) return;

        isChatBusy = true;
        sendBtn.disabled = true;
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Remove welcome message if present
        const welcome = chatMessages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        appendChatMessage('user', escapeHtml(message));

        try {
            const body = { message, session_id: chatSessionId };
            if (selectedAgentType) body.agent_type = selectedAgentType;

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

    // ==================== Project Creation ====================
    createProjectForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const projectName = document.getElementById('project-name').value.trim();
        const projectDescription = document.getElementById('project-description').value.trim();

        if (!projectName || !projectDescription) {
            showMessage('Please fill in both project name and description.', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('project_name', projectName);
        formData.append('project_description', projectDescription);

        showMessage('Creating project... This may take a while.', 'info');
        createProjectForm.querySelector('button[type="submit"]').disabled = true;

        try {
            const response = await fetch('/api/projects/create', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'started') {
                showMessage(`Project "${data.project_name}" is being created. Switch to Projects tab to view progress.`, 'success');
                await populateExistingProjects();
                setTimeout(() => {
                    document.querySelector('[data-view="projects"]').click();
                    existingProjectsSelect.value = data.project_name;
                    loadProject(data.project_name);
                }, 1000);
                createProjectForm.reset();
            } else {
                showMessage(`Error: ${data.message}`, 'error');
            }
        } catch (error) {
            showMessage('An error occurred while trying to create the project.', 'error');
        } finally {
            createProjectForm.querySelector('button[type="submit"]').disabled = false;
        }
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

        if (logEventSource) { logEventSource.close(); logEventSource = null; }

        addLogLine(`Loading project: ${projectName}`, 'info');
        await fetchFileTree(projectName);
        startLogStream(projectName);
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
                    break;
                case 'phase_complete':
                    addLogLine(`PHASE ${parsedEvent.phase} complete: ${parsedEvent.message}`, parsedEvent.status || 'success');
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
                    break;
                case 'error':
                    addLogLine(`ERROR: ${parsedEvent.message}`, 'error');
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

    async function selectFile(element, filePathRelative) {
        if (selectedFileElement) selectedFileElement.classList.remove('selected');
        element.classList.add('selected');
        selectedFileElement = element;

        currentFilePath = filePathRelative;
        currentFileNameSpan.textContent = filePathRelative;
        fileCodeDisplay.textContent = 'Loading file content...';

        try {
            const response = await fetch(`/api/projects/${currentProject}/file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path_relative: filePathRelative })
            });
            const data = await response.json();

            if (data.status === 'success') {
                currentFileContent = data.content;
                fileCodeDisplay.textContent = data.content;
                const ext = getFileExtension(filePathRelative);
                fileCodeDisplay.className = `language-${ext}`;
                if (ext === 'html' && previewTab.classList.contains('active')) updatePreview();
            } else {
                fileCodeDisplay.textContent = `Error: ${data.message}`;
                currentFileContent = null;
            }
        } catch (error) {
            fileCodeDisplay.textContent = 'An error occurred while reading file content.';
            currentFileContent = null;
        }
    }

    function getFileExtension(filename) {
        const parts = filename.split('.');
        if (parts.length > 1) {
            const ext = parts.pop().toLowerCase();
            const langMap = {
                'js': 'javascript', 'jsx': 'javascript', 'ts': 'javascript', 'tsx': 'javascript',
                'py': 'python', 'html': 'html', 'htm': 'html', 'css': 'css', 'scss': 'css',
                'json': 'json', 'xml': 'xml', 'md': 'markdown'
            };
            return langMap[ext] || ext;
        }
        return 'plaintext';
    }

    // ==================== Preview ====================
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
            benchEventSource = new EventSource('/api/benchmark/stream');

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
    const hljsTheme = document.getElementById('hljs-theme');

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ollash-theme', theme);
        if (theme === 'light') {
            themeIcon.textContent = '\u{1F319}';
            themeLabel.textContent = 'Dark Mode';
            hljsTheme.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css';
        } else {
            themeIcon.textContent = '\u{2600}\u{FE0F}';
            themeLabel.textContent = 'Light Mode';
            hljsTheme.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github-dark.min.css';
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

    // ==================== Syntax Highlighting ====================
    // Re-highlight code when a file is loaded in the code viewer
    const codeDisplay = document.getElementById('file-code-display');
    if (codeDisplay && typeof hljs !== 'undefined') {
        const observer = new MutationObserver(function () {
            // Detect language from file extension
            const fileName = document.getElementById('current-file-name');
            if (fileName) {
                const ext = fileName.textContent.split('.').pop().toLowerCase();
                const langMap = {
                    'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                    'html': 'xml', 'css': 'css', 'json': 'json', 'md': 'markdown',
                    'sh': 'bash', 'yml': 'yaml', 'yaml': 'yaml', 'toml': 'toml',
                    'rs': 'rust', 'go': 'go', 'java': 'java', 'rb': 'ruby',
                    'sql': 'sql', 'xml': 'xml', 'txt': 'plaintext',
                };
                const lang = langMap[ext] || '';
                codeDisplay.className = lang ? `language-${lang}` : '';
            }
            hljs.highlightElement(codeDisplay);
        });
        observer.observe(codeDisplay, { childList: true, characterData: true, subtree: true });
    }

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
});
