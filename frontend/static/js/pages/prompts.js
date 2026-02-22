// Prompt Studio with Monaco Editor and Repository Integration

const PromptStudio = {
    editor: null,
    currentRole: null,
    
    init: async function() {
        console.log("Initializing Prompt Studio...");
        this.setupMonaco();
        this.setupEventListeners();
        await this.loadRoles();
    },
    
    setupMonaco: function() {
        if (!window.monaco) {
            console.error("Monaco Editor not loaded.");
            return;
        }
        
        this.editor = monaco.editor.create(document.getElementById('prompt-monaco-container'), {
            value: "",
            language: 'yaml',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on'
        });
        
        this.editor.onDidChangeModelContent(() => {
            this.handleInput();
        });
    },
    
    setupEventListeners: function() {
        const saveBtn = document.getElementById('save-prompt-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.savePrompt());
        }
        
        const migrateBtn = document.getElementById('migrate-prompts-btn');
        if (migrateBtn) {
            migrateBtn.addEventListener('click', () => this.migratePrompts());
        }
    },
    
    loadRoles: async function() {
        try {
            const res = await fetch('/prompts/api/roles');
            const data = await res.json();
            const list = document.getElementById('prompt-role-list');
            list.innerHTML = '';
            
            data.roles.forEach(role => {
                const item = document.createElement('div');
                item.className = 'role-item';
                item.textContent = role;
                item.onclick = () => this.selectRole(role);
                list.appendChild(item);
            });
        } catch (e) {
            console.error("Failed to load roles", e);
        }
    },
    
    selectRole: async function(role) {
        this.currentRole = role;
        
        // Update active class
        document.querySelectorAll('.role-item').forEach(el => {
            el.classList.toggle('active', el.textContent === role);
        });
        
        try {
            const res = await fetch(`/prompts/api/load/${role}`);
            const data = await res.json();
            
            if (data.prompt) {
                this.editor.setValue(data.prompt);
                // Update language based on source or content
                const lang = data.prompt.trim().startsWith('{') ? 'json' : 'yaml';
                monaco.editor.setModelLanguage(this.editor.getModel(), lang);
            }
            
            await this.loadHistory(role);
        } catch (e) {
            console.error("Failed to load prompt for " + role, e);
        }
    },
    
    loadHistory: async function(role) {
        try {
            const res = await fetch(`/prompts/api/history/${role}`);
            const data = await res.json();
            const list = document.getElementById('prompt-version-list');
            list.innerHTML = '';
            
            if (data.history.length === 0) {
                list.innerHTML = '<p class="placeholder">No history found in DB.</p>';
                return;
            }
            
            data.history.forEach(v => {
                const item = document.createElement('div');
                item.className = `history-item ${v.is_active ? 'active' : ''}`;
                item.innerHTML = `
                    <span class="version">v${v.version}</span>
                    <span class="date">${new Date(v.created_at).toLocaleString()}</span>
                `;
                item.onclick = () => this.editor.setValue(v.prompt_text);
                list.appendChild(item);
            });
        } catch (e) {
            console.error("Failed to load history", e);
        }
    },
    
    savePrompt: async function() {
        if (!this.currentRole) {
            alert("Please select a role first.");
            return;
        }
        
        const promptText = this.editor.getValue();
        
        try {
            const res = await fetch('/prompts/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    role: this.currentRole,
                    prompt: promptText
                })
            });
            
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                await this.loadHistory(this.currentRole);
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            console.error("Save failed", e);
            alert("Fatal error during save.");
        }
    },
    
    handleInput: function() {
        // Debounced validation
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.validate(), 800);
    },
    
    validate: async function() {
        const text = this.editor.getValue();
        if (!text) return;
        
        try {
            const res = await fetch('/prompts/api/validate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ prompt: text })
            });
            const data = await res.json();
            // Optional: Render validation UI if present in templates
        } catch (e) {}
    }
};

// Initialize if view is present
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('prompt-monaco-container')) {
        PromptStudio.init();
    }
});
