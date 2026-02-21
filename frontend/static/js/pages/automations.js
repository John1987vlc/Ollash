/**
 * Automations Module for Ollash Agent
 */
window.AutomationsModule = (function() {
    let newAutomationBtn, automationModal, automationForm, automationsGrid, taskScheduleSelect, cronGroup;

    function init(elements) {
        newAutomationBtn = document.getElementById('new-automation-btn');
        automationModal = document.getElementById('automation-modal');
        automationForm = document.getElementById('automation-form');
        automationsGrid = document.getElementById('automations-grid');
        taskScheduleSelect = document.getElementById('task-schedule');
        cronGroup = document.getElementById('cron-group');

        if (newAutomationBtn) {
            newAutomationBtn.addEventListener('click', () => {
                if (automationModal) automationModal.style.display = 'flex';
            });
        }

        if (taskScheduleSelect) {
            taskScheduleSelect.addEventListener('change', (e) => {
                if (cronGroup) {
                    cronGroup.style.display = e.target.value === 'cron' ? 'block' : 'none';
                }
            });
        }

        if (automationForm) {
            automationForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await saveNewAutomation();
            });
        }

        // Close modal on outside click
        window.addEventListener('click', (e) => {
            if (e.target === automationModal) {
                automationModal.style.display = 'none';
            }
        });

        loadAutomations();
    }

    async function loadAutomations() {
        if (!automationsGrid) return;
        
        try {
            const response = await fetch('/api/automations');
            const tasks = await response.json();
            
            automationsGrid.innerHTML = '';
            
            if (tasks.length === 0) {
                automationsGrid.innerHTML = '<div class="no-automations">No scheduled tasks found.</div>';
                return;
            }

            tasks.forEach(task => {
                const card = document.createElement('div');
                card.className = `automation-card ${task.status}`;
                card.innerHTML = `
                    <div class="automation-info">
                        <h4>${escapeHtml(task.name)}</h4>
                        <p class="automation-meta">${escapeHtml(task.agent)} | ${escapeHtml(task.schedule)}</p>
                        <p class="automation-prompt">${escapeHtml(task.prompt.substring(0, 60))}...</p>
                    </div>
                    <div class="automation-actions">
                        <button class="btn-icon run-task" title="Run Now" data-id="${task.id}">▶</button>
                        <button class="btn-icon toggle-task" title="Toggle Status" data-id="${task.id}">${task.status === 'active' ? '⏸' : '⏵'}</button>
                        <button class="btn-icon delete-task" title="Delete" data-id="${task.id}">🗑</button>
                    </div>
                `;
                
                // Add event listeners to actions
                card.querySelector('.run-task').onclick = () => runTaskNow(task.id);
                card.querySelector('.toggle-task').onclick = () => toggleTask(task.id);
                card.querySelector('.delete-task').onclick = () => deleteTask(task.id);
                
                automationsGrid.appendChild(card);
            });
        } catch (error) {
            console.error('Error loading automations:', error);
        }
    }

    async function saveNewAutomation() {
        const formData = new FormData(automationForm);
        const data = {
            name: formData.get('name'),
            agent: formData.get('agent'),
            prompt: formData.get('prompt'),
            schedule: formData.get('schedule'),
            cron: formData.get('cron'),
            notifyEmail: formData.get('notifyEmail') === 'on'
        };

        try {
            const response = await fetch('/api/automations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                if (window.notificationService) notificationService.success('Automation created successfully');
                automationModal.style.display = 'none';
                automationForm.reset();
                loadAutomations();
            } else {
                const err = await response.json();
                if (window.notificationService) notificationService.error(err.error || 'Failed to create automation');
            }
        } catch (error) {
            console.error('Error saving automation:', error);
        }
    }

    async function runTaskNow(taskId) {
        try {
            await fetch(`/api/automations/${taskId}/run`, { method: 'POST' });
            if (window.notificationService) notificationService.info('Task execution started');
        } catch (error) {
            console.error('Error running task:', error);
        }
    }

    async function toggleTask(taskId) {
        try {
            await fetch(`/api/automations/${taskId}/toggle`, { method: 'PUT' });
            loadAutomations();
        } catch (error) {
            console.error('Error toggling task:', error);
        }
    }

    async function deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this automation?')) return;
        try {
            await fetch(`/api/automations/${taskId}`, { method: 'DELETE' });
            loadAutomations();
        } catch (error) {
            console.error('Error deleting task:', error);
        }
    }

    return {
        init: init,
        loadAutomations: loadAutomations
    };
})();
