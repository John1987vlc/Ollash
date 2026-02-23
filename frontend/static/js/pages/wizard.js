/**
 * Wizard Module for Project Creation
 */
window.WizardModule = (function() {
    let currentWizardStep = 1;
    let selectedTemplate = 'default';
    let isInitialized = false;
    
    // DOM Elements
    let wizardSteps, wizardIndicators, wizardNextBtns, wizardBackBtns, wizardGenerateBtn;
    let currentProjectName, currentProjectDescription, currentPythonVersion, currentLicenseType, currentIncludeDocker;
    let currentGeneratedStructure, currentGeneratedReadme;
    
    const phases = [
        { id: 'ProjectAnalysisPhase', label: 'Analysis' },
        { id: 'ReadmeGenerationPhase', label: 'README' },
        { id: 'StructureGenerationPhase', label: 'Structure' },
        { id: 'LogicPlanningPhase', label: 'Logic' },
        { id: 'StructurePreReviewPhase', label: 'Review 1' },
        { id: 'EmptyFileScaffoldingPhase', label: 'Scaffold' },
        { id: 'FileContentGenerationPhase', label: 'Generation' },
        { id: 'FileRefinementPhase', label: 'Refine' },
        { id: 'VerificationPhase', label: 'Verify' },
        { id: 'SecurityScanPhase', label: 'Security' },
        { id: 'LicenseCompliancePhase', label: 'License' },
        { id: 'TestGenerationExecutionPhase', label: 'Tests' },
        { id: 'SeniorReviewPhase', label: 'Final Review' }
    ];

    function init(elements) {
        wizardSteps = elements.wizardSteps;
        wizardIndicators = elements.wizardIndicators;
        wizardNextBtns = elements.wizardNextBtns;
        wizardBackBtns = elements.wizardBackBtns;
        wizardGenerateBtn = elements.wizardGenerateBtn;

        // Next button listeners
        wizardNextBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                if (validateStep(currentWizardStep)) wizardGoTo(currentWizardStep + 1);
            });
        });

        // Back button listeners
        wizardBackBtns.forEach(btn => {
            btn.addEventListener('click', () => wizardGoTo(currentWizardStep - 1));
        });

        if (wizardGenerateBtn) {
            wizardGenerateBtn.addEventListener('click', handleGenerateStructureSubmit);
        }

        const confirmStructureBtn = document.getElementById('confirm-structure-btn');
        if (confirmStructureBtn) {
            confirmStructureBtn.addEventListener('click', handleConfirmAndGenerate);
        }

        // Template Selection
        document.querySelectorAll('.template-card').forEach(card => {
            card.onclick = () => {
                document.querySelectorAll('.template-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                selectedTemplate = card.dataset.template;
            };
        });

        // GitHub Maintenance UI Logic
        const gitRepoUrlInput = document.getElementById('git-repo-url');
        const autoImproveGroup = document.getElementById('auto-improve-group');
        const autoImproveToggle = document.getElementById('auto-improve-enabled');
        const intervalGroup = document.getElementById('maintenance-interval-group');

        if (gitRepoUrlInput && autoImproveGroup) {
            gitRepoUrlInput.addEventListener('input', () => {
                const hasUrl = gitRepoUrlInput.value.trim().length > 0;
                autoImproveGroup.style.opacity = hasUrl ? '1' : '0.5';
                autoImproveGroup.style.pointerEvents = hasUrl ? 'auto' : 'none';
                if (!hasUrl) {
                    if (autoImproveToggle) autoImproveToggle.checked = false;
                    if (intervalGroup) intervalGroup.style.display = 'none';
                }
            });
        }

        if (autoImproveToggle && intervalGroup) {
            autoImproveToggle.addEventListener('change', () => {
                intervalGroup.style.display = autoImproveToggle.checked ? 'block' : 'none';
            });
        }

        // GitHub Section Toggle
        const githubHeader = document.getElementById('toggle-github-settings');
        const githubContent = document.getElementById('github-settings-content');
        if (githubHeader && githubContent) {
            githubHeader.onclick = (e) => {
                e.preventDefault();
                const isHidden = githubContent.style.display === 'none' || githubContent.style.display === '';
                githubContent.style.display = isHidden ? 'block' : 'none';
                
                const chevron = githubHeader.querySelector('.chevron');
                if (chevron) {
                    chevron.innerHTML = isHidden ? '&#x25BE;' : '&#x25B8;';
                }
            };
        }
        isInitialized = true;
    }

    function wizardGoTo(step) {
        if (step < 1 || step > wizardSteps.length) return;
        wizardSteps.forEach((el, i) => el.classList.toggle('active', (i + 1) === step));
        wizardIndicators.forEach((el, i) => {
            el.classList.toggle('active', (i + 1) === step);
            el.classList.toggle('completed', (i + 1) < step);
        });
        currentWizardStep = step;
    }

    function validateStep(step) {
        if (step === 1) {
            const name = document.getElementById('project-name').value.trim();
            if (!name) { alert("Please enter a project name."); return false; }
        }
        return true;
    }

    async function handleGenerateStructureSubmit(event) {
        if (event) event.preventDefault();
        currentProjectName = document.getElementById('project-name').value.trim();
        currentProjectDescription = document.getElementById('project-description').value.trim();

        if (!currentProjectName || !currentProjectDescription) {
            alert('Please fill in both project name and description.');
            return;
        }

        const formData = new FormData();
        formData.append('project_name', currentProjectName);
        formData.append('project_description', currentProjectDescription);
        formData.append('template_name', selectedTemplate);
        formData.append('python_version', document.getElementById('python-version').value);
        formData.append('license_type', document.getElementById('license-type').value);
        formData.append('include_docker', document.getElementById('include-docker').checked);
        formData.append('include_terraform', document.getElementById('include-terraform').checked);

        if (window.showMessage) window.showMessage('Generating project structure...', 'info');
        wizardGenerateBtn.disabled = true;

        try {
            const response = await fetch('/api/projects/generate_structure', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.status === 'structure_generated') {
                document.dispatchEvent(new CustomEvent('structureGenerated', { detail: data }));
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (error) {
            console.error('Error:', error);
        } finally {
            wizardGenerateBtn.disabled = false;
        }
    }

    async function handleConfirmAndGenerate() {
        const formData = new FormData();
        formData.append('project_name', currentProjectName);
        formData.append('project_description', currentProjectDescription);
        formData.append('template_name', selectedTemplate);
        formData.append('python_version', document.getElementById('python-version').value);
        formData.append('license_type', document.getElementById('license-type').value);
        formData.append('include_docker', document.getElementById('include-docker').checked);
        formData.append('include_terraform', document.getElementById('include-terraform').checked);
        
        // Git settings — derive git_push automatically from whether a URL was provided
        const gitRepoUrl = document.getElementById('git-repo-url')?.value?.trim() || '';
        formData.append('git_repo_url', gitRepoUrl);
        formData.append('git_token', document.getElementById('git-token')?.value || '');
        formData.append('git_branch', document.getElementById('git-branch')?.value?.trim() || 'main');
        formData.append('git_push', gitRepoUrl ? 'true' : 'false');
        formData.append('git_auto_create', document.getElementById('git-auto-create')?.checked ? 'true' : 'false');

        // Continuous Maintenance
        const maintenanceEnabled = document.getElementById('auto-improve-enabled')?.checked;
        formData.append('maintenance_enabled', maintenanceEnabled ? 'true' : 'false');
        formData.append('maintenance_interval', document.getElementById('maintenance-interval')?.value || '1');

        // Show pipeline UI
        document.getElementById('generated-structure-section').style.display = 'none';
        const pipelineView = document.getElementById('phase-pipeline-view');
        pipelineView.classList.add('active');
        renderPipeline();

        try {
            const response = await fetch('/api/projects/create', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.status === 'started') {
                startListening(currentProjectName);
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (error) {
            console.error('Error starting project creation:', error);
        }
    }

    function renderPipeline() {
        const container = document.getElementById('phase-steps-container');
        container.innerHTML = '';
        phases.forEach(phase => {
            const step = document.createElement('div');
            step.className = 'phase-step';
            step.id = `phase-${phase.id}`;
            step.innerHTML = `
                <div class="phase-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                </div>
                <div class="phase-label">${phase.label}</div>
            `;
            container.appendChild(step);
        });
    }

    function startListening(projectName) {
        const eventSource = new EventSource(`/api/projects/stream/${projectName}`);
        const logContainer = document.getElementById('phase-log-mini');
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const type = data.type || data.event;
            
            if (data.message) {
                const entry = document.createElement('div');
                entry.style.marginBottom = '4px';
                entry.innerHTML = `<span style="color:var(--accent-primary)">[${new Date().toLocaleTimeString()}]</span> ${data.message}`;
                logContainer.appendChild(entry);
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            if (type === 'milestone_started') {
                const phaseId = data.phase;
                document.querySelectorAll('.phase-step.active').forEach(s => {
                    s.classList.remove('active');
                    s.classList.add('completed');
                });
                const step = document.getElementById(`phase-${phaseId}`);
                if (step) step.classList.add('active');
            } else if (type === 'agent_board_update') {
                if (window.KanbanBoard) {
                    if (data.action === 'init_backlog') {
                        window.KanbanBoard.initBacklog(data.tasks);
                    } else if (data.action === 'move_task') {
                        window.KanbanBoard.moveTask(data.task_id, data.new_status);
                    }
                }
            } else if (type === 'project_complete' || type === 'stream_end') {
                document.querySelectorAll('.phase-step.active').forEach(s => {
                    s.classList.remove('active');
                    s.classList.add('completed');
                });
                eventSource.close();
            }
        };
        
        eventSource.onerror = () => eventSource.close();
    }

    return {
        init: init,
        goTo: wizardGoTo,
        get isInitialized() { return isInitialized; }
    };
})();
