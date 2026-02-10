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

    // ==================== Navigation ====================
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            const viewId = this.dataset.view;
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
            views.forEach(view => view.classList.remove('active'));
            document.getElementById(`${viewId}-view`).classList.add('active');
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
            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: chatSessionId })
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
                        // Show subtle iteration indicator
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
                        // Reset session so next message creates a fresh event bridge
                        chatSessionId = null;
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
        // Basic markdown-like formatting
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

    // Auto-resize textarea
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
        logEventSource = new EventSource(`/api/projects/stream/${projectName}`);

        logEventSource.onmessage = function(event) {
            const logLine = event.data;
            let logType = 'info';
            if (logLine.includes('[ERROR]') || logLine.toLowerCase().includes('error')) logType = 'error';
            else if (logLine.includes('[SUCCESS]') || logLine.toLowerCase().includes('complete')) logType = 'success';
            else if (logLine.includes('[WARNING]')) logType = 'warning';

            addLogLine(logLine, logType);

            if (logLine.includes('Creating new file:') || logLine.includes('PHASE')) {
                if (!window._ftDebounce) {
                    window._ftDebounce = setTimeout(() => {
                        fetchFileTree(projectName);
                        window._ftDebounce = null;
                    }, 500);
                }
            }
            if (logLine.includes('[STREAM_END]')) {
                logEventSource.close();
                logEventSource = null;
                addLogLine('Project generation completed!', 'success');
                fetchFileTree(projectName);
            }
        };

        logEventSource.onerror = function() {
            logEventSource.close();
            logEventSource = null;
            addLogLine('Lost connection to log stream', 'error');
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

    // ==================== Init ====================
    populateExistingProjects();
});
