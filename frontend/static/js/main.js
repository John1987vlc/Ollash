/**
 * Ollash Agent - Main Orchestrator
 * High-level orchestration, SPA routing, and global state management.
 */

// Global Helpers for Modals (called from HTML onclick)
window.closeAutomationModal = function() {
    const modal = document.getElementById('automation-modal');
    if (modal) modal.style.display = 'none';
};

window.closeNotificationModal = function() {
    const modal = document.getElementById('notification-config-modal');
    if (modal) modal.style.display = 'none';
};

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
            healthNetVal: document.getElementById('health-net-val')
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
            sendBtn: document.getElementById('send-btn')
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
            case 'docs': if (window.DocsModule) window.DocsModule.loadDocs(); break;
            case 'costs': if (window.CostModule) window.CostModule.updateCostsDashboard(); break;
            case 'architecture': if (window.ArchitectureModule) window.ArchitectureModule.loadArchitecture(); break;
            case 'brain': if (typeof loadBrainData !== 'undefined') loadBrainData(); break;
            case 'plugins': if (typeof loadPlugins !== 'undefined') loadPlugins(); break;
            case 'cicd': if (window.CICDModule) window.CICDModule.loadHistory(); break;
            case 'hil': if (window.HILModule) window.HILModule.refresh(); break;
        }
    }

    // ==================== Global Helpers ====================
    async function checkOllamaStatus() {
        if (!statusDot || !statusText) return;
        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            statusDot.style.background = (data.status === 'ok') ? 'var(--color-success)' : 'var(--color-error)';
            statusText.textContent = (data.status === 'ok') ? 'Ollama connected' : 'Ollama offline';
        } catch {
            statusDot.style.background = 'var(--color-error)';
            statusText.textContent = 'Ollama offline';
        }
    }

    // ==================== Theme Management ====================
    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ollash-theme', theme);
        if (window.monacoEditor) {
            monaco.editor.setTheme(theme === 'dark' ? 'vs-dark' : 'vs-light');
        }
    }

    if (themeToggle) {
        const savedTheme = localStorage.getItem('ollash-theme') || 'dark';
        setTheme(savedTheme);
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') || 'dark';
            setTheme(current === 'dark' ? 'light' : 'dark');
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
    setInterval(checkOllamaStatus, 30000);
    setInterval(() => {
        if (typeof HealthModule !== 'undefined' && HealthModule.fetchSystemHealth) HealthModule.fetchSystemHealth();
    }, 10000);

    // Global messaging bridge
    window.showMessage = function(msg, type) {
        if (window.notificationService) window.notificationService[type === 'error' ? 'error' : 'info'](msg);
        else console.log(`[${type}] ${msg}`);
    };
});
