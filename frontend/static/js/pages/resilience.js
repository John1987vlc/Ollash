/**
 * Resilience Monitor Module
 */
if (typeof window.refreshResilienceData === 'undefined') {
    async function refreshResilienceData() {
        const loopsCount = document.getElementById('loops-count');
        if (!loopsCount) return;

    try {
        const [statusRes, logsRes] = await Promise.all([
            fetch('/api/resilience/status'),
            fetch('/api/resilience/logs')
        ]);

        const status = await statusRes.json();
        const logs = await logsRes.json();

        // Update Metrics
        document.getElementById('loops-count').textContent = status.loops_detected || 0;
        document.getElementById('plans-count').textContent = status.contingency_plans_executed || 0;
        document.getElementById('health-score').textContent = (status.system_health_score || 0).toFixed(1) + '%';
        
        // Update Progress Bars
        document.getElementById('loops-progress').style.width = Math.min((status.loops_detected || 0) * 10, 100) + '%';
        document.getElementById('plans-progress').style.width = Math.min((status.contingency_plans_executed || 0) * 20, 100) + '%';

        // Populate Logs
        const logBody = document.getElementById('resilience-log-body');
        if (logBody) {
            logBody.innerHTML = '';
            logs.forEach(log => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${log.time}</td>
                    <td><span class="status-badge">${log.event}</span></td>
                    <td>${log.tool || '--'}</td>
                    <td>${log.action || '--'}</td>
                    <td>${log.status || 'Active'}</td>
                `;
                logBody.appendChild(row);
            });
        }

    } catch (error) {
        console.error('Error fetching resilience data:', error);
    }
}

    window.refreshResilienceData = refreshResilienceData;
}

