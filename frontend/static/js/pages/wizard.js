/**
 * Wizard Module for Ollash Project Creation
 * Handles step navigation, template selection, and project generation trigger.
 */
window.WizardModule = (function() {
    let state = {
        currentStep: 1,
        selectedTemplate: 'default',
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

        // --- Step 2 Logic ---
        const loopsSlider = document.getElementById('refinement-loops');
        const loopsBadge = document.getElementById('loops-value');
        if (loopsSlider && loopsBadge) {
            loopsSlider.oninput = function() {
                loopsBadge.textContent = this.value;
            };
        }

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

        const healingToggle = document.getElementById('auto-improve-enabled');
        const intervalGroup = document.getElementById('maintenance-interval-group');
        if (healingToggle) {
            healingToggle.onchange = function() {
                intervalGroup.style.display = this.checked ? 'block' : 'none';
            };
        }

        console.log("🚀 WizardModule V2 initialized");
    }

    function navigateToStep(step) {
        if (step < 1 || step > 3) return;
        
        // Simple validation for step 1
        if (state.currentStep === 1 && step === 2) {
            const name = document.getElementById('project-name').value.trim();
            if (!name) {
                window.NotificationToast?.show("Por favor, introduce un nombre para el proyecto", "error");
                return;
            }
        }

        state.currentStep = step;

        // Update UI Steps
        document.querySelectorAll('.wizard-step').forEach((el, idx) => {
            el.classList.toggle('active', (idx + 1) === step);
        });

        // Update Dots
        document.querySelectorAll('.wizard-step-dot').forEach((dot, idx) => {
            dot.classList.toggle('active', (idx + 1) === step);
            dot.classList.toggle('completed', (idx + 1) < step);
        });
    }

    async function triggerGeneration() {
        const name = document.getElementById('project-name').value.trim();
        const desc = document.getElementById('project-description').value.trim();
        const pythonVersion = document.getElementById('python-version').value;
        const license = document.getElementById('license-type').value;
        const useDocker = document.getElementById('include-docker').checked;
        
        if (!name || !desc) {
            window.NotificationToast?.show("Faltan campos obligatorios", "error");
            return;
        }

        const generateBtn = document.getElementById('wizard-generate');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '✨ Generando...';

        try {
            const response = await fetch('/api/auto_agent/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_name: name,
                    description: desc,
                    python_version: pythonVersion,
                    license: license,
                    include_docker: useDocker,
                    template: state.selectedTemplate
                })
            });

            const data = await response.json();
            if (data.status === 'started') {
                window.NotificationToast?.show("¡Proyecto iniciado! Redirigiendo...", "success");
                
                // Use the global navigation to go to projects view
                setTimeout(() => {
                    const projectsNav = document.querySelector('[data-view="projects"]');
                    if (projectsNav) projectsNav.click();
                    
                    // Trigger load in projects module
                    if (window.ProjectsModule) {
                        window.ProjectsModule.refreshProjects();
                        setTimeout(() => window.ProjectsModule.loadProject(name), 1000);
                    }
                }, 1500);
            } else {
                throw new Error(data.message);
            }
        } catch (err) {
            window.NotificationToast?.show(`Error: ${err.message}`, "error");
            generateBtn.disabled = false;
            generateBtn.innerHTML = '✨ Generar Estructura';
        }
    }

    return { init };
})();
