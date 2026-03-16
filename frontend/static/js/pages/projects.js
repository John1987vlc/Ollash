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
            const data = await response.json();
            // API returns {projects: [{name, path, modified}, ...]}
            const projectList = (data.projects || []).map(p => (typeof p === 'string' ? p : p.name));
            const currentValue = existingProjectsSelect.value;
            existingProjectsSelect.innerHTML = '<option value="">Select a project...</option>';
            projectList.forEach(name => {
                const option = document.createElement('option');
                option.value = name;
                option.textContent = name;
                existingProjectsSelect.appendChild(option);
            });
            if (currentValue && projectList.includes(currentValue)) {
                existingProjectsSelect.value = currentValue;
            }
            // Render visual card grid
            renderProjectCards(projectList);
        } catch (error) {
            console.error('Error populating projects:', error);
        }
    }

    function renderProjectCards(projectNames) {
        const grid = document.getElementById('project-cards-grid');
        if (!grid) return;

        // Clear skeleton placeholders
        grid.querySelectorAll('.project-card--skeleton').forEach(el => el.remove());
        // Remove previously rendered cards
        grid.querySelectorAll('.project-card:not(.project-card--skeleton)').forEach(el => el.remove());
        grid.querySelector('.project-hub-empty')?.remove();

        if (!projectNames || projectNames.length === 0) {
            grid.innerHTML = `
                <div class="project-hub-empty">
                    <span class="project-hub-empty-icon">&#x1f4c1;</span>
                    <h3>Sin proyectos aún</h3>
                    <p>Crea tu primer proyecto para empezar.</p>
                    <button class="btn btn-primary" data-view="create" style="margin-top:var(--spacing-md);">
                        Crear un Proyecto
                    </button>
                </div>`;
            return;
        }

        const activeVal = existingProjectsSelect?.value;
        projectNames.forEach(name => {
            const card = document.createElement('div');
            card.className = 'project-card' + (name === activeVal ? ' active' : '');
            card.dataset.project = name;
            card.innerHTML = `
                <div class="project-card-name">${name}</div>
                <div class="project-card-meta">
                    <span>Local</span>
                    <span class="project-card-status status-ready">Listo</span>
                </div>`;
            card.addEventListener('click', () => {
                // Update active state on cards
                grid.querySelectorAll('.project-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                // Update hidden select and trigger existing JS
                if (existingProjectsSelect) {
                    existingProjectsSelect.value = name;
                    existingProjectsSelect.dispatchEvent(new Event('change'));
                }
            });
            grid.appendChild(card);
        });
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

        // Auto-load README.md into preview tab if it exists
        const readmeCandidates = ['README.md', 'readme.md', 'OLLASH.md'];
        for (const candidate of readmeCandidates) {
            try {
                const r = await fetch(`/api/projects/${projectName}/file`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_path_relative: candidate }),
                });
                const d = await r.json();
                if (d.status === 'success') {
                    loadFileContent(candidate);
                    if (currentFileNameSpan) currentFileNameSpan.textContent = candidate;
                    break;
                }
            } catch (_) { /* file not found, try next */ }
        }
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
        const sorted = [...items].sort((a, b) => {
            if (a.type === b.type) return a.name.localeCompare(b.name);
            return a.type === 'directory' ? -1 : 1;
        });

        sorted.forEach(item => {
            const li = document.createElement('div');
            li.className = `file-tree-item ${item.type}`;
            li.dataset.path = item.path;
            li.style.cursor = 'pointer';
            
            const icon = item.type === 'directory' ? '📁' : (window.Utils ? Utils.getFileIcon(item.name) : '📄');
            li.innerHTML = `<span class="icon">${icon}</span> <span class="name">${item.name}</span>`;
            
            container.appendChild(li);

            if (item.type === 'directory' && item.children) {
                const subUl = document.createElement('div');
                subUl.className = 'tree-sub';
                subUl.style.display = 'none';
                subUl.style.paddingLeft = '15px';
                container.appendChild(subUl);
                buildTree(item.children, subUl);
                
                li.onclick = (e) => {
                    e.stopPropagation();
                    const isExpanded = subUl.style.display === 'block';
                    subUl.style.display = isExpanded ? 'none' : 'block';
                    li.classList.toggle('expanded', !isExpanded);
                };
            } else {
                li.onclick = (e) => {
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

        const ext = path.split('.').pop().toLowerCase();
        const isPreviewable = ext === 'html' || ext === 'md';

        if (isPreviewable) {
            // Open preview tab for HTML/MD files
            const previewTabBtn = document.querySelector('.tab-btn[data-tab="preview"]');
            if (previewTabBtn) previewTabBtn.click();
        } else {
            // Open code tab for everything else
            const codeTabBtn = document.querySelector('.tab-btn[data-tab="code"]');
            if (codeTabBtn) codeTabBtn.click();
        }

        // Load content into both editor and preview
        loadFileContent(path);
    }

    async function loadFileContent(path) {
        if (!currentProject) return;
        try {
            const resp = await fetch(`/api/projects/${currentProject}/file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path_relative: path }),
            });
            const data = await resp.json();
            if (data.status !== 'success') return;

            // Always populate the code editor
            if (window.editor) {
                window.editor.setValue(data.content);
            }

            // Additionally populate the preview pane for HTML and Markdown files
            const ext = path.split('.').pop().toLowerCase();
            const frame = document.getElementById('preview-frame');
            const mdDiv = document.getElementById('preview-md');
            const emptyDiv = document.getElementById('preview-empty');

            if (frame) frame.style.display = 'none';
            if (mdDiv) mdDiv.style.display = 'none';
            if (emptyDiv) emptyDiv.style.display = 'none';

            if (ext === 'html') {
                if (frame) {
                    // Use Blob URL so relative scripts/styles in the HTML can load
                    const blob = new Blob([data.content], { type: 'text/html' });
                    const url = URL.createObjectURL(blob);
                    frame.src = url;
                    frame.style.display = 'block';
                    frame.onload = () => URL.revokeObjectURL(url);
                }
            } else if (ext === 'md') {
                if (mdDiv && window.marked) {
                    mdDiv.innerHTML = window.marked.parse(data.content);
                    // Syntax-highlight any code blocks
                    if (window.hljs) {
                        mdDiv.querySelectorAll('pre code').forEach(b => window.hljs.highlightElement(b));
                    }
                    mdDiv.style.display = 'block';
                } else if (mdDiv) {
                    // Fallback: plain text if marked not available
                    mdDiv.textContent = data.content;
                    mdDiv.style.display = 'block';
                }
            } else {
                if (emptyDiv) emptyDiv.style.display = 'flex';
            }
        } catch (e) { console.error(e); }
    }

    function setupTabListeners() {
        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.onclick = function() {
                const tabId = this.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                const target = document.getElementById(`${tabId}-tab`);
                if (target) target.classList.add('active');
            };
        });
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
        
        // 1. Update Pipeline Visualization if phase data is present
        if (data.phase_index !== undefined) {
            updatePipeline(data.phase_index, data.status || 'active');
        } else if (data.message) {
            // Heuristic detection if phase_index is missing
            detectPhaseFromMessage(data.message);
        }

        const line = document.createElement('div');
        line.className = `log-line ${data.level?.toLowerCase() || 'info'}`;
        const ts = new Date().toLocaleTimeString();
        line.innerHTML = `<span class="log-ts">[${ts}]</span> <span class="log-msg">${escapeHtml(data.message)}</span>`;
        agentLogs.appendChild(line);
        agentLogs.scrollTop = agentLogs.scrollHeight;
    }

    function updatePipeline(index, status) {
        const steps = document.querySelectorAll('.pipeline-step');
        const overallStatus = document.getElementById('pipeline-overall-status');
        
        if (overallStatus) {
            if (status === 'active') overallStatus.textContent = 'Running...';
            else if (status === 'completed') overallStatus.textContent = 'Project Ready';
            else if (status === 'failed') overallStatus.textContent = 'Error Detected';
        }

        steps.forEach(step => {
            const stepIndex = parseInt(step.dataset.phase);
            step.classList.remove('active', 'pending', 'completed', 'failed');
            
            if (stepIndex < index) {
                step.classList.add('completed');
                step.querySelector('.step-icon').textContent = '✓';
            } else if (stepIndex === index) {
                if (status === 'failed') {
                    step.classList.add('failed');
                    step.querySelector('.step-icon').textContent = '✕';
                } else {
                    step.classList.add('active');
                    step.querySelector('.step-icon').textContent = index;
                }
            } else {
                step.classList.add('pending');
                step.querySelector('.step-icon').textContent = stepIndex;
            }
        });
    }

    function detectPhaseFromMessage(msg) {
        const lower = msg.toLowerCase();
        if (lower.includes("phase 1") || lower.includes("analyzing")) updatePipeline(1, 'active');
        else if (lower.includes("phase 2") || lower.includes("planning")) updatePipeline(2, 'active');
        else if (lower.includes("phase 3") || lower.includes("scaffolding")) updatePipeline(3, 'active');
        else if (lower.includes("phase 4") || lower.includes("generating")) updatePipeline(4, 'active');
        else if (lower.includes("phase 5") || lower.includes("refining")) updatePipeline(5, 'active');
        else if (lower.includes("phase 6") || lower.includes("testing")) updatePipeline(6, 'active');
        else if (lower.includes("phase 7") || lower.includes("security")) updatePipeline(7, 'active');
        else if (lower.includes("phase 8") || lower.includes("finalizing")) updatePipeline(8, 'active');
        else if (lower.includes("completed successfully")) updatePipeline(9, 'completed'); // Past last step
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
        refreshProjects: populateExistingProjects,
        getCurrentProject: () => currentProject,
        refreshFileTree: () => currentProject && fetchFileTree(currentProject)
    };
})();
