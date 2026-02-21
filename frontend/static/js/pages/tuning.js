// Tuning Studio logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadTuning() {
        const resp = await fetch('/api/tuning/config');
        const config = await resp.json();
        
        // Update sliders if they exist (we need to match IDs or select by name)
        // For now, let's just log and implement a few
        console.log("Current Tuning Config:", config);
    }

    async function loadShadowReport() {
        const resp = await fetch('/api/tuning/shadow-report');
        const report = await resp.json();
        const container = document.getElementById('shadow-eval-table');
        
        let html = '<table class="simple-table"><thead><tr><th>Model</th><th>Eval Count</th><th>Correction Rate</th><th>Severity</th></tr></thead><tbody>';
        for (const [model, data] of Object.entries(report.models)) {
            html += `
                <tr>
                    <td>${model}</td>
                    <td>${data.total_evaluations}</td>
                    <td>${(data.correction_rate * 100).toFixed(1)}%</td>
                    <td>${data.avg_severity.toFixed(2)}</td>
                </tr>
            `;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'tuning') {
            loadTuning();
            loadShadowReport();
        }
    });
});
