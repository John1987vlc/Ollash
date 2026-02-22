/**
 * Wizard Module for Project Creation
 */
window.WizardModule = (function() {
    let currentWizardStep = 1;
    let selectedTemplate = 'default';
    
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
        
        // Git settings
        formData.append('git_repo_url', document.getElementById('git-repo-url')?.value || '');
        formData.append('git_token', document.getElementById('git-token')?.value || '');

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
        goTo: wizardGoTo
    };
})();
