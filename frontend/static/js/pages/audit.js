// LLM Audit logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadLogs() {
        const resp = await fetch('/api/audit/llm');
        const data = await resp.json();
        const tbody = document.getElementById('audit-tbody');
        tbody.innerHTML = '';
        
        data.events.forEach(ev => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${ev.timestamp || '--'}</td>
                <td><span class="badge ${ev.event_type || ev.type}">${ev.event_type || ev.type}</span></td>
                <td>${ev.model || '--'}</td>
                <td>${ev.success !== undefined ? (ev.success ? '✅' : '❌') : '--'}</td>
                <td>${ev.latency_ms ? ev.latency_ms.toFixed(0) + 'ms' : '--'}</td>
                <td><button class="btn-secondary btn-small" onclick='viewAuditDetail(${JSON.stringify(ev)})'>View JSON</button></td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.viewAuditDetail = (ev) => {
        // We could use a modal, for now alert/console or a specific div
        const detail = JSON.stringify(ev, null, 2);
        const win = window.open("", "Audit Detail", "width=600,height=400");
        win.document.body.innerHTML = `<pre style="background:#1e1e1e;color:#fff;padding:20px;">${detail}</pre>`;
    };

    document.getElementById('refresh-audit-btn').onclick = loadLogs;

    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'audit') loadLogs();
    });
});
