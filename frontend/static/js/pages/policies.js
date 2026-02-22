// Policies & Governance (RBAC) Logic

const PoliciesModule = {
    init: function() {
        this.loadPolicies();
    },

    loadPolicies: async function() {
        // Mock data if backend not ready
        const data = [
            {role: 'Orchestrator', fs: true, net: true, cli: true, sec: true},
            {role: 'Coder', fs: true, net: true, cli: false, sec: false},
            {role: 'Network', fs: false, net: true, cli: true, sec: false},
            {role: 'Auditor', fs: true, net: false, cli: false, sec: true}
        ];

        // Try fetch real data
        try {
            // const res = await fetch('/api/policies/rbac');
            // const data = await res.json();
        } catch (e) {
            console.log('Using mock policy data');
        }

        this.renderTable(data);
    },

    renderTable: function(data) {
        const body = document.getElementById('rbac-body');
        body.innerHTML = '';

        data.forEach(role => {
            const row = document.createElement('tr');
            row.className = 'agent-row';
            row.innerHTML = `
                <td>${role.role}</td>
                <td>${this.createToggle(role.fs)}</td>
                <td>${this.createToggle(role.net)}</td>
                <td>${this.createToggle(role.cli)}</td>
                <td>${this.createToggle(role.sec)}</td>
            `;
            body.appendChild(row);
        });
    },

    createToggle: function(checked) {
        return `
            <label class="switch">
                <input type="checkbox" ${checked ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
        `;
    },
    
    savePolicies: function() {
        // Here we would iterate the table and POST the data
        window.showMessage('Permissions updated successfully', 'success');
    }
};

window.savePolicies = PoliciesModule.savePolicies;
document.addEventListener('DOMContentLoaded', () => PoliciesModule.init());
