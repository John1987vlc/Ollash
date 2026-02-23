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

            // Update Sidebar UI
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');

            // Switch Visibility
            views.forEach(view => {
                view.classList.toggle('active', view.id === `${viewId}-view`);
            });

            // Trigger Module Specific Loads
            triggerViewLoad(viewId);
        });
    });

    function triggerViewLoad(viewId) {
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
            case 'docs': if (window.DocsModule) window.DocsModule.loadDocs(); break;
            case 'costs': if (window.CostModule) window.CostModule.updateCostsDashboard(); break;
            case 'architecture': if (window.ArchitectureModule) window.ArchitectureModule.loadArchitecture(); break;
            case 'brain': if (typeof loadBrainData !== 'undefined') loadBrainData(); break;
            case 'plugins': if (typeof loadPlugins !== 'undefined') loadPlugins(); break;
            case 'cicd': if (window.CICDModule) window.CICDModule.loadHistory(); break;
            case 'hil': if (window.HILModule) window.HILModule.refresh(); break;
            case 'checkpoints': if (typeof loadCheckpoints !== 'undefined') loadCheckpoints(); break;
            case 'integrations': if (typeof loadIntegrations !== 'undefined') loadIntegrations(); break;
            case 'pair-programming': if (typeof loadPairProgramming !== 'undefined') loadPairProgramming(); break;
        }
    }

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

    // ==================== Initialization ====================
    checkOllamaStatus();
    setInterval(checkOllamaStatus, 15000); 

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
});
