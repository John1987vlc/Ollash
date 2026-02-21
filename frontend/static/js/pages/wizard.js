/**
 * Wizard Module for Project Creation
 */
window.WizardModule = (function() {
    let currentWizardStep = 1;
    let selectedTemplate = 'default';
    
    // DOM Elements will be mapped during init
    let wizardSteps, wizardIndicators, wizardNextBtns, wizardBackBtns, wizardGenerateBtn;
    let currentProjectName, currentProjectDescription, currentPythonVersion, currentLicenseType, currentIncludeDocker;
    let currentGeneratedStructure, currentGeneratedReadme;

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
    }

    function wizardGoTo(step) {
        if (step < 1 || step > wizardSteps.length) return;
        
        wizardSteps.forEach((el, i) => {
            el.classList.toggle('active', (i + 1) === step);
        });
        
        wizardIndicators.forEach((el, i) => {
            el.classList.toggle('active', (i + 1) === step);
            el.classList.toggle('completed', (i + 1) < step);
        });
        
        currentWizardStep = step;
    }

    function validateStep(step) {
        if (step === 1) {
            const name = document.getElementById('project-name').value.trim();
            if (!name) {
                alert("Please enter a project name.");
                return false;
            }
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

        currentPythonVersion = document.getElementById('python-version').value;
        currentLicenseType = document.getElementById('license-type').value;
        currentIncludeDocker = document.getElementById('include-docker').checked;

        const formData = new FormData();
        formData.append('project_name', currentProjectName);
        formData.append('project_description', currentProjectDescription);
        formData.append('template_name', selectedTemplate);
        formData.append('python_version', currentPythonVersion);
        formData.append('license_type', currentLicenseType);
        formData.append('include_docker', currentIncludeDocker);

        if (typeof showMessage === 'function') showMessage('Generating project structure...', 'info');
        wizardGenerateBtn.disabled = true;

        try {
            const response = await fetch('/api/projects/generate_structure', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'structure_generated') {
                currentGeneratedStructure = data.structure;
                currentGeneratedReadme = data.readme;
                
                // Show editor (handled by main.js via event or global state)
                document.dispatchEvent(new CustomEvent('structureGenerated', { detail: data }));
            } else {
                alert(`Error generating structure: ${data.message}`);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while trying to generate the project structure.');
        } finally {
            wizardGenerateBtn.disabled = false;
        }
    }

    return {
        init: init,
        goTo: wizardGoTo,
        getSelectedTemplate: () => selectedTemplate,
        setSelectedTemplate: (t) => { selectedTemplate = t; }
    };
})();
