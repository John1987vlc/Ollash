/**
 * Cybersecurity Page Logic
 * Handles port scanning, vulnerability scanning, log analysis, and hardening recommendations.
 * Extracted from security.html inline script.
 */
(function () {
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('run-port-scan')?.addEventListener('click', async () => {
            const host = document.getElementById('port-host').value;
            const common = document.getElementById('common-ports').checked;
            const resultsDiv = document.getElementById('port-results');

            resultsDiv.innerText = 'Scanning...';
            try {
                const response = await fetch('/api/cybersecurity/scan/ports', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ host, common_ports_only: common })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                resultsDiv.innerText = 'Error: ' + e.message;
            }
        });

        document.getElementById('run-vuln-scan')?.addEventListener('click', async () => {
            const path = document.getElementById('scan-path').value;
            const resultsDiv = document.getElementById('vuln-results');

            resultsDiv.innerText = 'Scanning...';
            try {
                const response = await fetch('/api/cybersecurity/scan/vulnerabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                resultsDiv.innerText = 'Error: ' + e.message;
            }
        });

        document.getElementById('run-log-analysis')?.addEventListener('click', async () => {
            const path = document.getElementById('log-path').value;
            const resultsDiv = document.getElementById('log-results');

            resultsDiv.innerText = 'Analyzing...';
            try {
                const response = await fetch('/api/cybersecurity/logs/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path })
                });
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                resultsDiv.innerText = 'Error: ' + e.message;
            }
        });

        document.getElementById('get-recommendations')?.addEventListener('click', async () => {
            const os = document.getElementById('os-type').value;
            const resultsDiv = document.getElementById('rec-results');

            resultsDiv.innerText = 'Fetching...';
            try {
                const response = await fetch(`/api/cybersecurity/recommendations?os=${encodeURIComponent(os)}`);
                const data = await response.json();
                resultsDiv.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                resultsDiv.innerText = 'Error: ' + e.message;
            }
        });
    });
}());
