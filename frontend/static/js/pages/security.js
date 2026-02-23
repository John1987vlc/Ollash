/**
 * Cybersecurity View Logic
 */
window.SecurityModule = (function() {
    let resultsContainer;

    function init() {
        resultsContainer = document.getElementById('security-results-container');
        
        const vulnBtn = document.getElementById('btn-vuln-scan');
        const portBtn = document.getElementById('btn-port-scan');
        const integrityBtn = document.getElementById('btn-integrity-check');
        const recoBtn = document.getElementById('btn-get-recommendations');

        if (vulnBtn) vulnBtn.onclick = runVulnerabilityScan;
        if (portBtn) portBtn.onclick = runPortScan;
        if (integrityBtn) integrityBtn.onclick = runIntegrityCheck;
        if (recoBtn) recoBtn.onclick = getRecommendations;
    }

    async function runVulnerabilityScan() {
        showLoading('Running vulnerability scan...');
        try {
            const res = await fetch('/api/cybersecurity/scan/vulnerabilities', { method: 'POST', body: JSON.stringify({}) });
            const data = await res.json();
            renderResults(data.vulnerabilities || [], 'Vulnerability Scan');
        } catch (e) { showError(e); }
    }

    async function runPortScan() {
        showLoading('Scanning common ports...');
        try {
            const res = await fetch('/api/cybersecurity/scan/ports', { method: 'POST', body: JSON.stringify({ host: 'localhost' }) });
            const data = await res.json();
            renderResults(data.open_ports || [], 'Port Scan');
        } catch (e) { showError(e); }
    }

    async function runIntegrityCheck() {
        showLoading('Checking system integrity...');
        try {
            const res = await fetch('/api/cybersecurity/integrity/check', { method: 'POST', body: JSON.stringify({}) });
            const data = await res.json();
            renderResults(data.changes || [], 'Integrity Check');
        } catch (e) { showError(e); }
    }

    async function getRecommendations() {
        showLoading('Fetching hardening recommendations...');
        try {
            const res = await fetch('/api/cybersecurity/recommendations');
            const data = await res.json();
            renderResults(data.recommendations || [], 'Hardening Recommendations');
        } catch (e) { showError(e); }
    }

    function renderResults(items, title) {
        resultsContainer.innerHTML = `<h4>${title}</h4>`;
        if (items.length === 0) {
            resultsContainer.innerHTML += '<p class="success-msg">No issues found!</p>';
            return;
        }
        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'vulnerability-item';
            div.innerHTML = `
                <strong>${item.title || item.issue || 'Discovery'}</strong>
                <p style="font-size:0.8rem; margin-top:5px;">${item.description || item.details || JSON.stringify(item)}</p>
            `;
            resultsContainer.appendChild(div);
        });
    }

    function showLoading(msg) {
        resultsContainer.innerHTML = `<div class="loading-spinner-small"></div><p>${msg}</p>`;
    }

    function showError(e) {
        resultsContainer.innerHTML = `<p class="error-msg">Error: ${e.message}</p>`;
    }

    return { init };
})();
