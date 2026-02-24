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

    function navigateToStep(step) {
        if (step < 1 || step > 3) return;

        if (state.currentStep === 1 && step === 2) {
            const name = document.getElementById('project-name').value.trim();
            if (!name) {
                window.NotificationToast?.show('Por favor, introduce un nombre para el proyecto', 'error');
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

    /** Open SSE connection and wire events to the Kanban board */
    function startSSE(projectName) {
        if (state.sseSource) {
            state.sseSource.close();
        }

        const es = new EventSource(`/api/projects/stream/${encodeURIComponent(projectName)}`);
        state.sseSource = es;

        // domain_orchestration_started — DAG nodes arrive, seed the Kanban
        es.addEventListener('domain_orchestration_started', (e) => {
            try {
                const data = JSON.parse(e.data);
                // Nothing to init yet; nodes arrive via task_status_changed
                console.log('[Wizard] Orchestration started', data);
            } catch (_) {}
        });

        // task_status_changed — move cards in the Kanban board
        es.addEventListener('task_status_changed', (e) => {
            try {
                const data = JSON.parse(e.data);
                const { task_id, status } = data;
                const statusMap = {
                    IN_PROGRESS: 'in_progress',
                    COMPLETED: 'done',
                    FAILED: 'done',
                    READY: 'todo',
                    PENDING: 'todo',
                };
                const kanbanStatus = statusMap[status] || 'todo';

                if (!document.getElementById(`task-card-${task_id}`)) {
                    // First time we see this task — add it to the backlog
                    window.KanbanBoard?.initBacklog([{ id: task_id, title: task_id, description: data.agent_type || '' }]);
                }
                window.KanbanBoard?.moveTask(task_id, kanbanStatus);

                // If failed, append error badge
                if (status === 'FAILED') {
                    const card = document.getElementById(`task-card-${task_id}`);
                    if (card && !card.querySelector('.task-error-badge')) {
                        const badge = document.createElement('span');
                        badge.className = 'task-error-badge';
                        badge.textContent = 'FAILED';
                        badge.style.cssText = 'background:var(--color-error);color:#fff;font-size:0.65rem;padding:2px 6px;border-radius:4px;margin-top:4px;display:inline-block;';
                        card.appendChild(badge);
                    }
                }
            } catch (_) {}
        });

        // task_remediation_queued — show orange REMEDIATION badge
        es.addEventListener('task_remediation_queued', (e) => {
            try {
                const data = JSON.parse(e.data);
                window.NotificationToast?.show(`Auto-sanación iniciada para: ${data.task_id || ''}`, 'warning');
            } catch (_) {}
        });

        // domain_orchestration_completed — celebrate
        es.addEventListener('domain_orchestration_completed', (e) => {
            try {
                const data = JSON.parse(e.data);
                window.NotificationToast?.show('Proyecto generado con éxito', 'success');
                es.close();
                setTimeout(() => {
                    const projectsNav = document.querySelector('[data-view="projects"]');
                    if (projectsNav) projectsNav.click();
                    if (window.ProjectsModule) {
                        window.ProjectsModule.refreshProjects();
                        setTimeout(() => window.ProjectsModule.loadProject(projectName), 1000);
                    }
                }, 1500);
            } catch (_) {}
        });

        es.onerror = () => {
            // SSE may close naturally after stream_end; no action needed
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
            if (data.status === 'started') {
                state.currentProjectName = formData.project_name;
                window.NotificationToast?.show('Proyecto iniciado — siguiendo progreso...', 'info');

                // Show Kanban and start listening for events
                const board = document.getElementById('kanban-board');
                if (board) board.style.display = 'flex';

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
