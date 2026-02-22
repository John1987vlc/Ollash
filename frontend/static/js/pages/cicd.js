/**
 * CI/CD & Maintenance Dashboard Logic
 */

const CICDModule = (function() {
    // --- Elements ---
    let ciLogInput, analyzeBtn, fixBtn, analysisResults, ciCategory, ciConfidence, ciRootCause, ciSuggestions;
    let maintTimeline, runMaintBtn;

    function init() {
        console.log("Initializing CICDModule...");
        
        // Cache elements
        ciLogInput = document.getElementById('ci-log-input');
        analyzeBtn = document.getElementById('analyze-ci-btn');
        fixBtn = document.getElementById('fix-ci-btn');
        analysisResults = document.getElementById('ci-analysis-results');
        ciCategory = document.getElementById('ci-category');
        ciConfidence = document.getElementById('ci-confidence');
        ciRootCause = document.getElementById('ci-root-cause-text');
        ciSuggestions = document.getElementById('ci-suggestions-list');
        
        maintTimeline = document.getElementById('maint-timeline');
        runMaintBtn = document.getElementById('run-maintenance-now');

        // Events
        if (analyzeBtn) analyzeBtn.addEventListener('click', analyzeCILog);
        if (fixBtn) fixBtn.addEventListener('click', generateCIFix);
        if (runMaintBtn) runMaintBtn.addEventListener('click', runMaintenanceNow);

        // Load Initial Data
        fetchMaintenanceHistory();
    }

    async function analyzeCILog() {
        const log = ciLogInput.value.trim();
        if (!log) {
            NotificationService.error("Por favor, pega un log de error para analizar.");
            return;
        }

        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analizando...";

        try {
            const response = await fetch('/api/cicd/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ log: log })
            });

            const data = await response.json();
            
            if (data.error) {
                NotificationService.error("Error al analizar el log: " + data.error);
                return;
            }

            displayAnalysis(data.analysis);
            fixBtn.disabled = false;
        } catch (error) {
            console.error("Analysis failed:", error);
            NotificationService.error("Fallo la conexión con el servidor.");
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Analizar Fallo";
        }
    }

    function displayAnalysis(analysis) {
        analysisResults.style.display = 'block';
        ciCategory.textContent = analysis.category || 'unknown';
        ciConfidence.textContent = Math.round((analysis.confidence || 0.7) * 100) + '%';
        ciRootCause.textContent = analysis.root_cause || 'No se pudo determinar la causa raíz.';
        
        // Render suggestions
        ciSuggestions.innerHTML = '';
        if (analysis.suggested_fixes && analysis.suggested_fixes.length > 0) {
            analysis.suggested_fixes.forEach(fix => {
                const li = document.createElement('li');
                li.style.fontSize = '0.85rem';
                li.style.marginTop = '4px';
                li.textContent = fix;
                ciSuggestions.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = "No hay sugerencias automáticas disponibles.";
            ciSuggestions.appendChild(li);
        }

        // Add badges based on category
        ciCategory.className = 'badge';
        if (analysis.category === 'dependency') ciCategory.classList.add('info');
        else if (analysis.category === 'test') ciCategory.classList.add('warning');
        else if (analysis.category === 'build') ciCategory.classList.add('error');
    }

    async function generateCIFix() {
        const log = ciLogInput.value.trim();
        fixBtn.disabled = true;
        fixBtn.textContent = "Generando Fix...";

        try {
            const response = await fetch('/api/cicd/fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ log: log })
            });

            const data = await response.json();
            
            if (data.error) {
                NotificationService.error("Error al generar el fix: " + data.error);
                return;
            }

            // In a real scenario, this might show a diff or create a PR
            console.log("Fix generated:", data.fix);
            NotificationService.success("¡Fix generado con éxito! Revisa la consola para ver los detalles.");
            
            // Trigger a modal or side panel to show the fix (placeholder)
            if (window.ArtifactRenderer) {
                window.ArtifactRenderer.renderArtifact({
                    type: 'code',
                    title: 'CI/CD Auto-Fix Suggestion',
                    content: JSON.stringify(data.fix, null, 2),
                    language: 'json'
                });
            }
        } catch (error) {
            NotificationService.error("Error de red al generar el fix.");
        } finally {
            fixBtn.disabled = false;
            fixBtn.textContent = "Generar Fix Automático";
        }
    }

    async function runMaintenanceNow() {
        runMaintBtn.disabled = true;
        NotificationService.info("Iniciando ciclo de mantenimiento autónomo...");

        try {
            // Note: This endpoint might vary based on your automation_bp setup
            const response = await fetch('/api/automations/autonomous_maintenance_hourly/run', {
                method: 'POST'
            });

            if (response.ok) {
                NotificationService.success("Mantenimiento iniciado en segundo plano.");
                setTimeout(fetchMaintenanceHistory, 5000); // Refresh history after a few seconds
            } else {
                NotificationService.error("No se pudo iniciar el mantenimiento.");
            }
        } catch (error) {
            NotificationService.error("Error al conectar con el servicio de mantenimiento.");
        } finally {
            runMaintBtn.disabled = false;
        }
    }

    async function fetchMaintenanceHistory() {
        if (!maintTimeline) return;

        try {
            // Mocking some data if no real history endpoint exists yet
            // In a real app, you'd fetch this from a DB or logs
            const history = [
                { id: 'maint-123', status: 'success', title: 'Optimización de Imports', date: 'Hace 45 min', issues: 5, fixes: 5 },
                { id: 'maint-122', status: 'success', title: 'Limpieza de Código Muerto', date: 'Hace 1h 45 min', issues: 2, fixes: 2 },
                { id: 'maint-121', status: 'error', title: 'Fallo en Generación de Tests', date: 'Hace 2h 45 min', issues: 8, fixes: 0 }
            ];

            maintTimeline.innerHTML = '';
            history.forEach(item => {
                const div = document.createElement('div');
                div.className = `timeline-item ${item.status}`;
                div.innerHTML = `
                    <div class="timeline-content">
                        <h5>${item.title}</h5>
                        <p>${item.issues} problemas encontrados, ${item.fixes} correcciones aplicadas.</p>
                        <div class="meta">${item.date} | ID: ${item.id}</div>
                    </div>
                `;
                maintTimeline.appendChild(div);
            });
        } catch (error) {
            console.error("Failed to fetch maintenance history:", error);
        }
    }

    return {
        init: init,
        loadHistory: fetchMaintenanceHistory
    };
})();

// Register on load if on the right page or via main orchestrator
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('cicd-view')) {
        CICDModule.init();
    }
});
