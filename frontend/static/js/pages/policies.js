// Policies logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadPolicies() {
        const resp = await fetch('/api/policies');
        const policies = await resp.json();
        
        const commandsList = document.getElementById('policy-commands-list');
        commandsList.innerHTML = '';
        policies.allowed_commands.forEach(cmd => {
            const span = document.createElement('span');
            span.className = 'tag';
            span.textContent = cmd;
            commandsList.appendChild(span);
        });

        const pathsList = document.getElementById('policy-paths-list');
        pathsList.innerHTML = '';
        policies.critical_paths.forEach(path => {
            const span = document.createElement('span');
            span.className = 'tag critical';
            span.textContent = path;
            pathsList.appendChild(span);
        });
    }

    window.addPolicyCommand = async () => {
        const input = document.getElementById('new-command-input');
        const cmd = input.value.trim();
        if (!cmd) return;
        
        const resp = await fetch('/api/policies');
        const policies = await resp.json();
        policies.allowed_commands.push(cmd);
        
        await fetch('/api/policies/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ allowed_commands: policies.allowed_commands })
        });
        
        input.value = '';
        loadPolicies();
    };

    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'policies') loadPolicies();
    });
});
