/**
 * Wizard Module for Ollash Project Creation
 * Handles step navigation, template selection, and project generation trigger.
 * Collects all available configuration options and wires the Kanban board
 * to real-time task_status_changed SSE events from DomainAgentOrchestrator.
 */
window.WizardModule = (function() {
    let state = {
        currentStep: 1,
        selectedTemplate: 'default',
        currentProjectName: null,
        sseSource: null,
        elements: {}
    };

    function init(elements) {
        state.elements = elements;

        // Navigation Buttons
        document.querySelectorAll('.wizard-next-btn').forEach(btn => {
            btn.onclick = () => navigateToStep(state.currentStep + 1);
        });

        document.querySelectorAll('.wizard-back-btn').forEach(btn => {
            btn.onclick = () => navigateToStep(state.currentStep - 1);
        });

        // Template Selection
        document.querySelectorAll('.template-card-v2').forEach(card => {
            card.onclick = function() {
                document.querySelectorAll('.template-card-v2').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                state.selectedTemplate = this.dataset.template;
            };
        });

        // Final Generate Button
        const generateBtn = document.getElementById('wizard-generate');
        if (generateBtn) {
            generateBtn.onclick = triggerGeneration;
        }

        // --- Step 2 sliders ---
        const loopsSlider = document.getElementById('refinement-loops');
        const loopsBadge = document.getElementById('loops-value');
        if (loopsSlider && loopsBadge) {
            loopsSlider.oninput = function() { loopsBadge.textContent = this.value; };
        }

        const poolSlider = document.getElementById('pool-size');
        const poolBadge = document.getElementById('pool-size-value');
        if (poolSlider && poolBadge) {
            poolSlider.oninput = function() { poolBadge.textContent = this.value; };
        }

        // GitHub mode conditional fields
        const githubMode = document.getElementById('github-mode');
        const githubFields = document.getElementById('github-fields');
        const repoUrlField = document.getElementById('repo-url-field');
        if (githubMode) {
            githubMode.onchange = function() {
                const val = this.value;
                githubFields.style.display = val === 'none' ? 'none' : 'block';
                repoUrlField.style.display = val === 'existing' ? 'block' : 'none';
            };
        }

        // Auto-healing interval visibility
        const healingToggle = document.getElementById('auto-improve-enabled');
        const intervalGroup = document.getElementById('maintenance-interval-group');
        if (healingToggle) {
            healingToggle.onchange = function() {
                intervalGroup.style.display = this.checked ? 'block' : 'none';
            };
        }

        console.log('WizardModule V2 initialized');
    }

    const NAME_PATTERN = /^[a-zA-Z0-9_\-]+$/;

    function navigateToStep(step) {
        if (step < 1 || step > 3) return;

        if (state.currentStep === 1 && step === 2) {
            const nameEl = document.getElementById('project-name');
            const name = nameEl ? nameEl.value.trim() : '';
            if (!name) {
                window.NotificationToast?.show('Introduce un nombre para el proyecto', 'error');
                nameEl?.focus();
                return;
            }
            if (!NAME_PATTERN.test(name)) {
                window.NotificationToast?.show('El nombre solo puede contener letras, números, _ y - (sin espacios)', 'error');
                nameEl?.focus();
                return;
            }
        }

        state.currentStep = step;

        document.querySelectorAll('.wizard-step').forEach((el, idx) => {
            el.classList.toggle('active', (idx + 1) === step);
        });

        document.querySelectorAll('.wizard-step-dot').forEach((dot, idx) => {
            dot.classList.toggle('active', (idx + 1) === step);
            dot.classList.toggle('completed', (idx + 1) < step);
        });
    }

    /** Collect all form values — visible and accordion fields */
    function collectFormData() {
        const g = id => document.getElementById(id);
        const checked = id => { const el = g(id); return el ? el.checked : false; };
        const val = id => { const el = g(id); return el ? el.value : ''; };
        const num = (id, def) => { const el = g(id); return el ? (parseInt(el.value, 10) || def) : def; };

        return {
            project_name: g('project-name')?.value.trim() || '',
            project_description: g('project-description')?.value.trim() || '',
            template: state.selectedTemplate,
            // Stack & Infra
            python_version: val('python-version'),
            license_type: val('license-type'),
            include_docker: checked('include-docker'),
            include_terraform: checked('include-terraform'),
            num_refine_loops: num('refinement-loops', 1),
            // GitHub
            github_mode: val('github-mode'),
            git_token: val('git-token'),
            git_repo_url: val('git-repo-url'),
            // Maintenance
            maintenance_enabled: checked('auto-improve-enabled'),
            maintenance_interval: num('maintenance-interval', 1),
            // Advanced: Agents & Performance
            pool_size: num('pool-size', 3),
            timeout: num('task-timeout', 300),
            parallel_generation_enabled: checked('parallel-generation'),
            // Advanced: Quality & Security
            security_scanning_enabled: checked('security-scanning'),
            block_security_critical: checked('block-on-critical'),
            checkpoint_enabled: checked('checkpoint-enabled'),
            cost_tracking_enabled: checked('cost-tracking'),
            senior_review_as_pr: checked('senior-review-pr'),
            enable_github_wiki: checked('github-wiki'),
            enable_github_pages: checked('github-pages'),
            // Feature Flags
            feature_feedback_refinement: checked('feat-feedback-refinement'),
            feature_refactoring: checked('feat-refactoring'),
            feature_load_testing: checked('feat-load-testing'),
            feature_license_scan: checked('feat-license-scan'),
            feature_cicd_healing: checked('feat-cicd-healing'),
        };
    }

    // ── Progress panel helpers ─────────────────────────────────────────────

    function showProgressPanel(projectName) {
        // Hide all wizard steps
        document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.wizard-step-dot').forEach(d => {
            d.classList.remove('active');
            d.classList.add('completed');
        });

        const panel = document.getElementById('wizard-step-generating');
        if (panel) {
            panel.style.display = 'block';
            const nameEl = document.getElementById('progress-project-name');
            if (nameEl) nameEl.textContent = projectName;
        }
    }

    function logLine(text, type) {
        const log = document.getElementById('generation-log');
        if (!log) return;
        const line = document.createElement('div');
        const color = type === 'error' ? 'var(--color-error)' : type === 'success' ? 'var(--color-success)' : 'var(--color-text-secondary)';
        line.style.cssText = `color:${color}; padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.04);`;
        line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        log.appendChild(line);
        log.scrollTop = log.scrollHeight;
    }

    function setPhaseLabel(text) {
        const el = document.getElementById('generation-current-phase');
        if (el) el.textContent = text;
    }

    function showDone(projectName) {
        setPhaseLabel('¡Completado!');
        const spinner = document.querySelector('#generation-status .generation-spinner');
        if (spinner) spinner.style.display = 'none';
        const doneEl = document.getElementById('generation-done');
        doneEl.style.display = 'block';
        doneEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

        function _goToProject() {
            const nav = document.querySelector('[data-view="projects"]');
            if (nav) nav.click();
            if (window.ProjectsModule) {
                window.ProjectsModule.refreshProjects();
                setTimeout(() => window.ProjectsModule.loadProject(projectName), 800);
            }
        }

        const viewBtn = document.getElementById('view-project-btn');
        if (viewBtn) {
            viewBtn.onclick = _goToProject;
            viewBtn.focus();
        }

        // Auto-redirect after 3 seconds so the user lands on the project page
        // without having to click the button.
        setTimeout(_goToProject, 3000);
    }

    function showError(msg) {
        setPhaseLabel('Error durante la generación');
        const spinner = document.querySelector('#generation-status .generation-spinner');
        if (spinner) spinner.style.display = 'none';
        const errPanel = document.getElementById('generation-error');
        if (errPanel) {
            errPanel.style.display = 'block';
            const errMsg = errPanel.querySelector('.generation-error-msg');
            if (errMsg) errMsg.textContent = msg || '';
        }

        const retryBtn = document.getElementById('retry-generation-btn');
        if (retryBtn) {
            retryBtn.onclick = () => {
                document.getElementById('wizard-step-generating').style.display = 'none';
                navigateToStep(1);
                const generateBtn = document.getElementById('wizard-generate');
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.innerHTML = '✨ Generar Estructura';
                }
            };
        }
    }

    // ── SSE ────────────────────────────────────────────────────────────────

    function startSSE(projectName) {
        if (state.sseSource) state.sseSource.close();

        const es = new EventSource(`/api/projects/stream/${encodeURIComponent(projectName)}`);
        state.sseSource = es;

        // Generic message fallback
        es.onmessage = (e) => {
            try {
                const d = JSON.parse(e.data);
                const msg = d.message || d.phase || JSON.stringify(d);
                logLine(msg);
            } catch (_) { logLine(e.data); }
        };

        es.addEventListener('phase_start', (e) => {
            try {
                const d = JSON.parse(e.data);
                const phase = d.phase || d.message || '';
                setPhaseLabel(`Fase: ${phase}`);
                logLine(`▶ ${phase}`, 'info');
            } catch (_) {}
        });

        es.addEventListener('phase_complete', (e) => {
            try {
                const d = JSON.parse(e.data);
                logLine(`✔ ${d.phase || d.message || ''}`, 'success');
            } catch (_) {}
        });

        es.addEventListener('task_status_changed', (e) => {
            try {
                const d = JSON.parse(e.data);
                const label = `${d.task_id || ''} → ${d.status || ''}`;
                logLine(label, d.status === 'FAILED' ? 'error' : 'info');
                if (d.status === 'IN_PROGRESS') setPhaseLabel(d.task_id || '');
            } catch (_) {}
        });

        es.addEventListener('log', (e) => {
            try { logLine(JSON.parse(e.data).message || e.data); } catch (_) { logLine(e.data); }
        });

        es.addEventListener('stream_end', (e) => {
            logLine('Pipeline completado', 'success');
            es.close();
            showDone(projectName);
            window.NotificationToast?.show('Proyecto generado con éxito', 'success');
        });

        es.addEventListener('domain_orchestration_completed', (e) => {
            logLine('Orquestación completada', 'success');
            es.close();
            showDone(projectName);
            window.NotificationToast?.show('Proyecto generado con éxito', 'success');
        });

        es.addEventListener('error_event', (e) => {
            try {
                const d = JSON.parse(e.data);
                logLine(d.message || 'Error desconocido', 'error');
                showError(d.message);
            } catch (_) {}
        });

        es.onerror = (e) => {
            // SSE closes naturally on stream end — only treat as error if we haven't finished
            if (document.getElementById('generation-done')?.style.display === 'none') {
                logLine('Conexión SSE cerrada', 'error');
                showError('Conexión perdida con el servidor');
            }
        };
    }

    async function triggerGeneration() {
        const formData = collectFormData();

        if (!formData.project_name || !formData.project_description) {
            window.NotificationToast?.show('Faltan campos obligatorios', 'error');
            return;
        }

        const generateBtn = document.getElementById('wizard-generate');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '✨ Generando...';

        // Map github_mode → git flags expected by /api/projects/create
        const gitPush = formData.github_mode !== 'none';
        const gitAutoCreate = formData.github_mode === 'new';

        const payload = {
            project_name: formData.project_name,
            project_description: formData.project_description,
            template_name: formData.template,
            python_version: formData.python_version,
            license_type: formData.license_type,
            include_docker: formData.include_docker,
            include_terraform: formData.include_terraform,
            num_refine_loops: formData.num_refine_loops,
            git_push: gitPush,
            git_auto_create: gitAutoCreate,
            git_token: formData.git_token,
            git_repo_url: formData.git_repo_url,
            maintenance_enabled: formData.maintenance_enabled,
            maintenance_interval: formData.maintenance_interval,
            pool_size: formData.pool_size,
            timeout: formData.timeout,
            parallel_generation_enabled: formData.parallel_generation_enabled,
            security_scanning_enabled: formData.security_scanning_enabled,
            block_security_critical: formData.block_security_critical,
            checkpoint_enabled: formData.checkpoint_enabled,
            cost_tracking_enabled: formData.cost_tracking_enabled,
            senior_review_as_pr: formData.senior_review_as_pr,
            enable_github_wiki: formData.enable_github_wiki,
            enable_github_pages: formData.enable_github_pages,
            feature_flags: {
                feedback_refinement: formData.feature_feedback_refinement,
                refactoring_enabled: formData.feature_refactoring,
                load_testing_enabled: formData.feature_load_testing,
                license_scanning_deep: formData.feature_license_scan,
                cicd_auto_healing: formData.feature_cicd_healing,
            },
        };

        try {
            const response = await fetch('/api/projects/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const data = await response.json();

            if (!response.ok) {
                // FastAPI validation errors have data.detail (array or string)
                const detail = data.detail;
                let msg;
                if (Array.isArray(detail)) {
                    msg = detail.map(e => `${e.loc?.slice(1).join('.')}: ${e.msg}`).join(' | ');
                } else {
                    msg = String(detail || data.message || `HTTP ${response.status}`);
                }
                throw new Error(msg);
            }

            if (data.status === 'started') {
                state.currentProjectName = formData.project_name;
                showProgressPanel(formData.project_name);
                logLine(`Proyecto "${formData.project_name}" iniciado...`, 'info');
                startSSE(formData.project_name);
            } else {
                throw new Error(data.message || 'Error desconocido');
            }
        } catch (err) {
            window.NotificationToast?.show(`Error: ${err.message}`, 'error');
            generateBtn.disabled = false;
            generateBtn.innerHTML = '✨ Generar Estructura';
        }
    }

    return { init };
})();
