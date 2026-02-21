// Prompt Studio logic
document.addEventListener('DOMContentLoaded', () => {
    let promptEditor = null;
    let currentRole = null;

    // Initialize Monaco Editor
    if (typeof monaco !== 'undefined') {
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.29.1/min/vs' } });
        require(['vs/editor/editor.main'], function () {
            promptEditor = monaco.editor.create(document.getElementById('prompt-monaco-container'), {
                value: '',
                language: 'markdown',
                theme: 'vs-dark',
                automaticLayout: true,
                minimap: { enabled: false }
            });
        });
    }

    async function loadRoles() {
        const resp = await fetch('/api/prompts/roles');
        const data = await resp.json();
        const list = document.getElementById('prompt-role-list');
        list.innerHTML = '';
        data.roles.forEach(role => {
            const btn = document.createElement('button');
            btn.className = 'role-item';
            btn.textContent = role;
            btn.onclick = () => selectRole(role, btn);
            list.appendChild(btn);
        });
    }

    async function selectRole(role, btn) {
        currentRole = role;
        document.querySelectorAll('.role-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const resp = await fetch(`/api/prompts/${role}/history`);
        const data = await resp.json();
        renderHistory(data.history);
        
        // Set editor value to active prompt
        const active = data.history.find(h => h.is_active);
        if (active && promptEditor) {
            promptEditor.setValue(active.prompt_text);
        }
    }

    function renderHistory(history) {
        const list = document.getElementById('prompt-version-list');
        list.innerHTML = '';
        history.forEach(item => {
            const div = document.createElement('div');
            div.className = `version-item ${item.is_active ? 'active' : ''}`;
            div.innerHTML = `
                <span>V${item.version} - ${new Date(item.created_at).toLocaleString()}</span>
                <button class="btn-icon" title="Rollback" onclick="rollbackPrompt(${item.id})">↺</button>
            `;
            div.onclick = () => {
                if (promptEditor) promptEditor.setValue(item.prompt_text);
            };
            list.appendChild(div);
        });
    }

    window.rollbackPrompt = async (id) => {
        if (confirm('Rollback to this version?')) {
            await fetch(`/api/prompts/rollback/${id}`, { method: 'POST' });
            if (currentRole) {
                const activeBtn = Array.from(document.querySelectorAll('.role-item')).find(b => b.textContent === currentRole);
                selectRole(currentRole, activeBtn);
            }
        }
    };

    document.getElementById('save-prompt-btn').onclick = async () => {
        if (!currentRole) return alert('Select a role first');
        const text = promptEditor.getValue();
        const resp = await fetch(`/api/prompts/${currentRole}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt_text: text })
        });
        const data = await resp.json();
        if (data.status === 'success') {
            alert('Prompt saved and activated');
            const activeBtn = Array.from(document.querySelectorAll('.role-item')).find(b => b.textContent === currentRole);
            selectRole(currentRole, activeBtn);
        }
    };

    document.getElementById('migrate-prompts-btn').onclick = async () => {
        const resp = await fetch('/api/prompts/migrate', { method: 'POST' });
        alert('Migration started');
        loadRoles();
    };

    // Load roles on init if view is active
    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'prompts') loadRoles();
    });
});
