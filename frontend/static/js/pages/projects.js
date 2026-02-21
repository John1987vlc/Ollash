/**
 * Projects Module for Ollash Agent
 * Handles project selection, file tree navigation, tab management, and security reports.
 */
window.ProjectsModule = (function() {
    let currentProject = null;
    let logEventSource = null;
    let selectedFileElement = null;
    let currentFilePath = null;
    let openTabs = [];
    let activeTabId = null;

    // DOM Elements
    let existingProjectsSelect, fileTreeList, agentLogs, projectWorkspace;
    let currentFileNameSpan, monacoEditorContainer;

    function init(elements) {
        existingProjectsSelect = elements.existingProjectsSelect;
        fileTreeList = elements.fileTreeList;
        agentLogs = elements.agentLogs;
        projectWorkspace = elements.projectWorkspace;
        currentFileNameSpan = document.getElementById('current-file-name');
        monacoEditorContainer = document.getElementById('monaco-editor-container');

        if (existingProjectsSelect) {
            existingProjectsSelect.addEventListener('change', function() {
                if (this.value) loadProject(this.value);
                else if (projectWorkspace) projectWorkspace.style.display = 'none';
            });
        }

        const refreshBtn = document.getElementById('refresh-files');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                if (currentProject) fetchFileTree(currentProject);
            });
        }

        // Initialize Tab System
        setupTabListeners();

        populateExistingProjects();
        console.log("🚀 ProjectsModule initialized");
    }

    async function populateExistingProjects() {
        if (!existingProjectsSelect) return;
        try {
            const response = await fetch('/api/projects/list');
            const projects = await response.json();
            if (projects.status === 'success') {
                const currentValue = existingProjectsSelect.value;
                existingProjectsSelect.innerHTML = '<option value="">Select a project...</option>';
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
        } catch (error) {
            console.error('Error populating projects:', error);
        }
    }

    async function loadProject(projectName) {
        currentProject = projectName;
        if (projectWorkspace) projectWorkspace.style.display = 'block';
        
        // Load tree
        await fetchFileTree(projectName);
        
        // Start logs
        startLogStream(projectName);
        
        // Load other data
        if (window.loadQuarantineList) window.loadQuarantineList(projectName);
        if (window.loadComplianceData) window.loadComplianceData(projectName);
    }

    async function fetchFileTree(projectName) {
        if (!fileTreeList) return;
        fileTreeList.innerHTML = '<div class="loading">Loading tree...</div>';
        try {
            const response = await fetch(`/api/projects/${projectName}/files`);
            const data = await response.json();
            if (data.status === 'success') {
                renderFileTree(data.files);
            }
        } catch (error) {
            console.error('Error fetching file tree', error);
            fileTreeList.innerHTML = '<div class="error">Error loading tree</div>';
        }
    }

    function renderFileTree(files) {
        if (!fileTreeList) return;
        fileTreeList.innerHTML = '';
        const treeRoot = document.createElement('ul');
        treeRoot.className = 'tree-root';
        
        buildTree(files, treeRoot);
        fileTreeList.appendChild(treeRoot);
    }

    function buildTree(items, container) {
        // Sort: folders first
        const sorted = [...items].sort((a, b) => {
            if (a.type === b.type) return a.name.localeCompare(b.name);
            return a.type === 'directory' ? -1 : 1;
        });

        sorted.forEach(item => {
            const li = document.createElement('li');
            li.className = `tree-item ${item.type}`;
            li.dataset.path = item.path;
            
            const label = document.createElement('div');
            label.className = 'tree-label';
            const icon = item.type === 'directory' ? '📁' : (window.Utils ? Utils.getFileIcon(item.name) : '📄');
            label.innerHTML = `<span class="icon">${icon}</span> <span class="name">${item.name}</span>`;
            
            li.appendChild(label);
            container.appendChild(li);

            if (item.type === 'directory' && item.children) {
                const subUl = document.createElement('ul');
                subUl.className = 'tree-sub';
                li.appendChild(subUl);
                buildTree(item.children, subUl);
                
                label.onclick = (e) => {
                    e.stopPropagation();
                    li.classList.toggle('expanded');
                };
            } else {
                label.onclick = (e) => {
                    e.stopPropagation();
                    selectFile(li, item.path);
                };
            }
        });
    }

    function selectFile(element, path) {
        if (selectedFileElement) selectedFileElement.classList.remove('selected');
        if (element) {
            element.classList.add('selected');
            selectedFileElement = element;
        }
        
        currentFilePath = path;
        if (currentFileNameSpan) currentFileNameSpan.textContent = path;
        
        // Open in editor (tabs)
        if (typeof createTab === 'function') createTab(path);
    }

    function startLogStream(projectName) {
        if (logEventSource) logEventSource.close();
        logEventSource = new EventSource(`/api/projects/stream/${projectName}`);
        logEventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                appendLog(data);
            } catch (e) {}
        };
    }

    function appendLog(data) {
        if (!agentLogs) return;
        const line = document.createElement('div');
        line.className = `log-line ${data.level?.toLowerCase() || 'info'}`;
        const ts = new Date().toLocaleTimeString();
        line.innerHTML = `<span class="log-ts">[${ts}]</span> <span class="log-msg">${escapeHtml(data.message)}</span>`;
        agentLogs.appendChild(line);
        agentLogs.scrollTop = agentLogs.scrollHeight;
    }

    function setupTabListeners() {
        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const tabId = this.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                const target = document.getElementById(`${tabId}-tab`);
                if (target) target.classList.add('active');
            });
        });
    }

    return {
        init: init,
        loadProject: loadProject,
        getCurrentProject: () => currentProject,
        refreshFileTree: () => currentProject && fetchFileTree(currentProject)
    };
})();
