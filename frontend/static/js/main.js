/**
 * Ollash Agent - Main Orchestrator
 * High-level orchestration, SPA routing, and global state management.
 */

document.addEventListener('DOMContentLoaded', function() {
    // ==================== DOM Elements ====================
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-indicator span');
    const themeToggle = document.getElementById('theme-toggle');

    // ==================== Global State ====================
    window.monacoEditor = null;

    // ==================== Module Initialization ====================
    
    // Core Utilities & Health
    if (typeof HealthModule !== 'undefined') {
        HealthModule.init({
            healthCpuBar: document.getElementById('health-cpu'),
            healthRamBar: document.getElementById('health-ram'),
            healthDiskBar: document.getElementById('health-disk'),
            healthCpuVal: document.getElementById('health-cpu-val'),
            healthRamVal: document.getElementById('health-ram-val'),
            healthDiskVal: document.getElementById('health-disk-val'),
            healthNetVal: document.getElementById('health-net-val'),
            healthChartCanvas: document.getElementById('health-history-chart')
        });
    }

    // Global Notifications
    if (typeof NotificationsModule !== 'undefined') {
        NotificationsModule.init();
    }

    // Docs Module
    if (typeof DocsModule !== 'undefined') {
        DocsModule.init();
    }

    // Cost Module
    if (typeof CostModule !== 'undefined') {
        CostModule.init();
    }

    // Chat Service Logic
    if (typeof ChatModule !== 'undefined') {
        ChatModule.init({
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendBtn: document.getElementById('send-btn'),
            voiceBtn: document.getElementById('voice-input-btn'),
            attachBtn: document.getElementById('attach-file-btn')
        });
    }

    // Chat Page UI Logic
    if (typeof ChatPageModule !== 'undefined') {
        ChatPageModule.init();
    }

    // Automations Module
    if (typeof AutomationsModule !== 'undefined') {
        AutomationsModule.init();
    }

    // Brain Module (NEW)
    if (typeof BrainModule !== 'undefined') {
        // Handled via triggerViewLoad
    }

    // Project Creation Wizard
    if (typeof WizardModule !== 'undefined') {
        WizardModule.init({
            wizardSteps: document.querySelectorAll('.wizard-step'),
            wizardIndicators: document.querySelectorAll('.wizard-step-indicator'),
            wizardNextBtns: document.querySelectorAll('.wizard-next-btn'),
            wizardBackBtns: document.querySelectorAll('.wizard-back-btn'),
            wizardGenerateBtn: document.getElementById('wizard-generate')
        });
    }

    // Project Workspace Management
    if (typeof ProjectsModule !== 'undefined') {
        ProjectsModule.init({
            existingProjectsSelect: document.getElementById('existing-projects'),
            fileTreeList: document.getElementById('file-tree-list'),
            agentLogs: document.getElementById('agent-logs'),
            projectWorkspace: document.getElementById('project-workspace')
        });
    }

    // CI/CD & Maintenance
    if (typeof CICDModule !== 'undefined') {
        CICDModule.init();
    }

    // HIL Approval Center
    if (typeof HILModule !== 'undefined') {
        HILModule.init();
    }

    // Benchmark Module
    if (typeof BenchmarkModule !== 'undefined') {
        BenchmarkModule.init({
            benchOllamaUrl: document.getElementById('bench-ollama-url'),
            benchFetchModels: document.getElementById('bench-fetch-models'),
            benchModelList: document.getElementById('bench-model-list'),
            benchStartBtn: document.getElementById('bench-start-btn'),
            benchOutput: document.getElementById('bench-output'),
            benchHistoryList: document.getElementById('bench-history-list')
        });
    }

    // Cost Module
    if (typeof CostModule !== 'undefined') {
        CostModule.init();
    }

    // Architecture Module
    if (typeof ArchitectureModule !== 'undefined') {
        ArchitectureModule.init();
    }

    // Swarm Module
    if (typeof SwarmModule !== 'undefined') {
        SwarmModule.init();
    }

    // Handle Wizard Completion
    document.addEventListener('structureGenerated', function(e) {
        const data = e.detail;
        const wizardContainer = document.getElementById('wizard-container');
        const structureSection = document.getElementById('generated-structure-section');
        
        if (wizardContainer) wizardContainer.style.display = 'none';
        if (structureSection) structureSection.style.display = 'block';
        
        // Initialize Structure Editor
        if (typeof StructureEditor !== 'undefined') {
            const editor = new StructureEditor('structure-editor-tree');
            editor.setStructure(data.structure);
            window.activeStructureEditor = editor;
        }
    });

    // Terminal Module
    if (typeof TerminalModule !== 'undefined') {
        TerminalModule.init({
            terminalContainer: document.getElementById('terminal-container'),
            floatingTerminal: document.getElementById('floating-terminal')
        });
    }

    // ==================== Monaco Editor Setup ====================
    const editorContainer = document.getElementById('monaco-editor-container');
    if (editorContainer && typeof require !== 'undefined') {
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.29.1/min/vs' }});
        require(['vs/editor/editor.main'], function() {
            window.monacoEditor = monaco.editor.create(editorContainer, {
                value: '// Welcome to Ollash Editor',
                language: 'plaintext',
                theme: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light',
                automaticLayout: true,
                minimap: { enabled: false }
            });
        });
    }

    // ==================== Sidebar Accordion ====================
    const navGroups = document.querySelectorAll('.nav-group');
    
    navGroups.forEach(group => {
        const header = group.querySelector('.nav-group-header');
        header.addEventListener('click', (e) => {
            group.classList.toggle('expanded');
            // Keep aria-expanded in sync with the visual state
            header.setAttribute('aria-expanded', group.classList.contains('expanded') ? 'true' : 'false');
        });

        // Auto-expand if it contains the active item
        if (group.querySelector('.nav-item.active')) {
            group.classList.add('expanded');
            header.setAttribute('aria-expanded', 'true');
        }
    });

    // ==================== SPA Router ====================
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            const viewId = this.dataset.view;
            if (!viewId) return;

            // Show page load bar (replaces full-screen spinner)
            showPageLoad();
            // Keep legacy loader hidden (backward compat — other code may reference it)
            const loader = document.getElementById('global-page-loader');
            if (loader) loader.style.display = 'none';

            // Update Sidebar UI
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');

            // Update Header Title
            const titleEl = document.getElementById('current-view-title');
            if (titleEl) {
                const label = this.querySelector('span')?.textContent || 'Dashboard';
                titleEl.textContent = label;
            }

            // Switch Visibility
            views.forEach(view => {
                view.classList.toggle('active', view.id === `${viewId}-view`);
            });

            // Trigger Module Specific Loads
            triggerViewLoad(viewId);
        });
    });

    // Delegated handler for [data-view] buttons outside the sidebar nav (e.g. CTAs in help page)
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-view]:not(.nav-item)');
        if (!btn) return;
        var viewId = btn.dataset.view;
        if (!viewId) return;
        var navItem = document.querySelector('.nav-item[data-view="' + viewId + '"]');
        if (navItem) navItem.click();
    });

    // ==================== Page Load Bar ====================
    const _pageLoadBar = document.getElementById('page-load-bar');
    function showPageLoad() {
        if (!_pageLoadBar) return;
        _pageLoadBar.classList.remove('complete');
        void _pageLoadBar.offsetWidth; // force reflow
        _pageLoadBar.classList.add('loading');
        setTimeout(() => {
            _pageLoadBar.classList.remove('loading');
            _pageLoadBar.classList.add('complete');
            setTimeout(() => _pageLoadBar.classList.remove('complete'), 600);
        }, 400);
    }

    // ==================== Mode Badge ====================
    const _modeBadge = document.getElementById('mode-badge');
    const _modeBadgeLabel = document.getElementById('mode-badge-label');
    function updateModeBadge(mode, label) {
        if (!_modeBadge) return;
        _modeBadge.style.display = 'inline-flex';
        _modeBadge.className = 'mode-badge mode-' + mode;
        if (_modeBadgeLabel) _modeBadgeLabel.textContent = label;
    }
    function hideModeBadge() {
        if (_modeBadge) _modeBadge.style.display = 'none';
    }

    function triggerViewLoad(viewId) {
        // Update mode badge per view
        if (viewId === 'chat') updateModeBadge('chat', 'Chat');
        else if (viewId === 'create') updateModeBadge('agent', 'Crear');
        else if (viewId === 'auto-agent') updateModeBadge('agent', 'Auto Agent');
        else hideModeBadge();

        switch(viewId) {
            case 'chat':
                if (window.ChatModule) ChatModule.init({
                    chatMessages: document.getElementById('chat-messages'),
                    chatInput: document.getElementById('chat-input'),
                    sendBtn: document.getElementById('send-btn')
                });
                if (window.ChatPageModule) ChatPageModule.init();
                break;
            case 'create':
                // Re-initialize to ensure listeners are attached to new DOM elements in SPA
                setTimeout(() => {
                    if (window.WizardModule) {
                        WizardModule.init({
                            wizardSteps: document.querySelectorAll('.wizard-step'),
                            wizardIndicators: document.querySelectorAll('.wizard-step-indicator'),
                            wizardNextBtns: document.querySelectorAll('.wizard-next-btn'),
                            wizardBackBtns: document.querySelectorAll('.wizard-back-btn'),
                            wizardGenerateBtn: document.getElementById('wizard-generate')
                        });
                    }
                }, 100);
                break;
            case 'brain': if (typeof loadBrainData !== 'undefined') loadBrainData(); break;
            case 'swarm': if (window.SwarmModule) window.SwarmModule.init(); break;
            case 'projects': if (window.ProjectsModule) window.ProjectsModule.refreshProjects(); break;
            case 'operations': if (typeof loadJobs !== 'undefined') loadJobs(); break;
            case 'resilience': if (typeof refreshResilienceData !== 'undefined') refreshResilienceData(); break;
            case 'insights': if (typeof loadInsightsData !== 'undefined') loadInsightsData(); break;
            case 'git': if (window.GitModule) window.GitModule.init(); break;
            case 'automations': if (window.AutomationsModule) window.AutomationsModule.loadAutomations(); break;
            case 'architecture': if (window.ArchitectureModule) window.ArchitectureModule.loadArchitecture(); break;
            case 'docs': if (window.DocsModule) window.DocsModule.loadDocs(); break;
            case 'costs': if (window.CostModule) window.CostModule.updateCostsDashboard(); break;
            case 'security': if (window.SecurityModule) window.SecurityModule.init(); break;
            case 'audit': if (window.AuditModule) window.AuditModule.init(); break;
            case 'policies': if (window.PoliciesModule) window.PoliciesModule.init(); break;
            case 'benchmark': if (window.BenchmarkModule) window.BenchmarkModule.init(); break;
            case 'analytics': if (window.AnalyticsDashboard) window.AnalyticsDashboard.init(); break;
            case 'checkpoints': if (typeof loadCheckpoints !== 'undefined') loadCheckpoints(); break;
            case 'integrations': if (window.IntegrationsModule) window.IntegrationsModule.init(); break;
            case 'knowledge': if (typeof loadKnowledgeData !== 'undefined') loadKnowledgeData(); break;
            case 'decisions': if (typeof loadDecisions !== 'undefined') loadDecisions(); break;
            case 'pair-programming': if (typeof loadPairProgramming !== 'undefined') loadPairProgramming(); break;
            case 'sandbox': {
                const sbView = document.getElementById('sandbox-view');
                if (sbView) sbView.classList.add('active');
                break;
            }
            case 'help':
                // Página de ayuda estática — sin módulo JS adicional
                break;
        }
    }

    // ==================== Project Context (Proyecto Activo) ====================

    function setActiveProject(name) {
        window.activeProject = name || null;
        const group = document.getElementById('nav-group-project');
        const label = document.getElementById('active-project-label');
        if (!group) return;

        if (name) {
            group.style.display = 'block';
            group.classList.add('expanded');
            const header = group.querySelector('.nav-group-header');
            if (header) header.setAttribute('aria-expanded', 'true');
            if (label) label.textContent = name;
        } else {
            group.style.display = 'none';
            group.classList.remove('expanded');
        }
    }

    // Watch the project selector in the Projects view
    const projectSelectEl = document.getElementById('existing-projects');
    if (projectSelectEl) {
        projectSelectEl.addEventListener('change', function() {
            setActiveProject(this.value || null);
        });
    }

    // Expose globally so other modules can call it
    window.setActiveProject = setActiveProject;

    // ==================== Global Helpers ====================
    async function checkOllamaStatus() {
        if (!statusDot || !statusText) return;
        const start = performance.now();
        const latencyLabel = document.querySelector('#latency-indicator .label');
        const latencyDot = document.querySelector('#latency-indicator .dot');

        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            const latency = Math.round(performance.now() - start);
            
            statusDot.style.background = (data.status === 'ok') ? 'var(--color-success)' : 'var(--color-error)';
            statusText.textContent = (data.status === 'ok') ? 'Ollama connected' : 'Ollama offline';
            
            if (latencyLabel) latencyLabel.textContent = `Ollama: ${latency} ms`;
            if (latencyDot) {
                latencyDot.style.background = latency < 100 ? 'var(--color-success)' : (latency < 500 ? 'var(--color-warning)' : 'var(--color-error)');
            }
        } catch {
            statusDot.style.background = 'var(--color-error)';
            statusText.textContent = 'Ollama offline';
            if (latencyLabel) latencyLabel.textContent = 'Ollama: Offline';
        }
    }

    function checkCostThreshold() {
        const totalTokens = parseInt(localStorage.getItem('session-tokens') || '0');
        const threshold = parseInt(document.getElementById('token-budget')?.value || '50000');
        
        if (totalTokens > threshold) {
            document.body.classList.add('cost-alert-active');
            window.showMessage('Token budget exceeded!', 'warning');
        } else {
            document.body.classList.remove('cost-alert-active');
        }
    }

    // ==================== Theme Management ====================
    // ThemeManager handles persistence, data-theme attribute, and aria-pressed.
    // We add Monaco Editor integration here since ThemeManager doesn't know about it.
    if (window.ThemeManager) {
        ThemeManager.init();
        OllashStore.subscribe('theme', function(theme) {
            if (window.monacoEditor && typeof monaco !== 'undefined') {
                monaco.editor.setTheme(theme === 'dark' ? 'vs-dark' : 'vs-light');
            }
        });
    } else if (themeToggle) {
        // Fallback if ThemeManager hasn't loaded
        const savedTheme = localStorage.getItem('ollash-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('ollash-theme', next);
        });
    }

    // ==================== Mobile Sidebar Toggle ====================
    const hamburgerBtn = document.getElementById('sidebar-hamburger');
    const sidebarEl = document.getElementById('main-sidebar');
    const sidebarOverlayEl = document.getElementById('sidebar-overlay');

    function openMobileSidebar() {
        sidebarEl.classList.add('sidebar--open');
        sidebarOverlayEl.classList.add('sidebar-overlay--visible');
        sidebarOverlayEl.removeAttribute('aria-hidden');
        hamburgerBtn.setAttribute('aria-expanded', 'true');
        hamburgerBtn.setAttribute('aria-label', 'Cerrar menú de navegación');
    }

    function closeMobileSidebar() {
        sidebarEl.classList.remove('sidebar--open');
        sidebarOverlayEl.classList.remove('sidebar-overlay--visible');
        sidebarOverlayEl.setAttribute('aria-hidden', 'true');
        hamburgerBtn.setAttribute('aria-expanded', 'false');
        hamburgerBtn.setAttribute('aria-label', 'Abrir menú de navegación');
    }

    if (hamburgerBtn && sidebarEl && sidebarOverlayEl) {
        hamburgerBtn.addEventListener('click', () => {
            if (sidebarEl.classList.contains('sidebar--open')) {
                closeMobileSidebar();
            } else {
                openMobileSidebar();
            }
        });

        sidebarOverlayEl.addEventListener('click', closeMobileSidebar);

        // Close sidebar when a nav item is selected on mobile
        sidebarEl.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) closeMobileSidebar();
            });
        });
    }

    // ==================== Desktop Sidebar Collapse ====================
    const SIDEBAR_EXPANDED_KEY = 'ollash-sidebar-expanded';
    const collapseToggleBtn = document.getElementById('sidebar-collapse-toggle');
    const logoBtn = document.getElementById('sidebar-logo-btn');

    function setSidebarExpanded(expanded) {
        if (!sidebarEl) return;
        sidebarEl.classList.toggle('sidebar--expanded', expanded);
        localStorage.setItem(SIDEBAR_EXPANDED_KEY, expanded ? '1' : '0');
        if (collapseToggleBtn) {
            collapseToggleBtn.setAttribute('aria-label', expanded ? 'Colapsar navegación' : 'Expandir navegación');
        }
    }

    // Restore persisted state; default collapsed
    const savedExpanded = localStorage.getItem(SIDEBAR_EXPANDED_KEY);
    setSidebarExpanded(savedExpanded === '1');

    if (collapseToggleBtn) {
        collapseToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            setSidebarExpanded(!sidebarEl.classList.contains('sidebar--expanded'));
        });
    }

    // Clicking the logo also expands the sidebar when collapsed
    if (logoBtn) {
        logoBtn.addEventListener('click', (e) => {
            if (!sidebarEl.classList.contains('sidebar--expanded')) {
                e.preventDefault();
                setSidebarExpanded(true);
            }
        });
    }

    // ==================== Initialization ====================
    checkOllamaStatus();
    setInterval(checkOllamaStatus, 15000); 

    // Global Benchmark Tracker
    if (window.BenchmarkService) {
        const benchIndicator = document.getElementById('global-benchmark-status');
        const benchStatusText = benchIndicator?.querySelector('.status-text');

        window.BenchmarkService.addListener((event) => {
            if (!benchIndicator) return;

            if (event.type === 'model_start' || event.type === 'task_start') {
                benchIndicator.style.display = 'flex';
                if (benchStatusText) {
                    benchStatusText.textContent = event.type === 'model_start' 
                        ? `Testing: ${event.model}`
                        : `Task: ${event.task}`;
                }
            } else if (event.type === 'benchmark_done' || event.type === 'error' || event.type === 'stream_end') {
                setTimeout(() => {
                    benchIndicator.style.display = 'none';
                }, 3000);
            }
        });
    }

    async function fetchSystemMetrics() {
        if (typeof HealthModule === 'undefined') return;
        try {
            const resp = await fetch('/api/health/');
            if (!resp.ok) return;
            const data = await resp.json();
            HealthModule.updateMetrics(data);
        } catch (err) {}
    }
    fetchSystemMetrics();
    setInterval(fetchSystemMetrics, 5000);
    setInterval(checkCostThreshold, 60000);

    // Terminal Bubble Listener
    const termBubble = document.getElementById('terminal-bubble');
    if (termBubble) {
        termBubble.addEventListener('click', () => {
            if (window.TerminalModule) window.TerminalModule.toggle();
        });
    }

    // Toolbox (Active Tools) listeners
    document.querySelectorAll('.tool-toggle input').forEach(input => {
        input.addEventListener('change', async (e) => {
            const tool = e.target.dataset.tool;
            const enabled = e.target.checked;
            
            try {
                await fetch('/api/settings/tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tool, enabled })
                });
            } catch(e) {}
            
            const count = document.querySelectorAll('.tool-toggle input:checked').length;
            const counter = document.getElementById('active-tools-count');
            if (counter) counter.textContent = count;
        });
    });

    // Global messaging bridge — delegates to NotificationToast if available
    window.showMessage = function(msg, type) {
        if (window.NotificationToast) {
            NotificationToast.show(msg, type || 'info');
        } else if (window.notificationService) {
            window.notificationService[type === 'error' ? 'error' : 'info'](msg);
        } else {
            console.log(`[${type}] ${msg}`);
        }
    };

    // Initialize component managers
    if (window.ModalManager) ModalManager.init();
    if (window.ConfirmDialog) ConfirmDialog.init();
    if (window.BenchmarkModal) BenchmarkModal.init();
});
