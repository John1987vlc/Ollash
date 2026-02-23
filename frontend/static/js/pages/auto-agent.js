/**
 * AutoAgent Kanban Board
 * Manages the Kanban board UI for agile task visualization.
 * Extracted from auto_agent.html inline script.
 */
window.KanbanBoard = (function () {
    function updateCounters() {
        ['todo', 'in_progress', 'done'].forEach(status => {
            const container = document.getElementById(`tasks-${status}`);
            const countEl = document.getElementById(`count-${status}`);
            if (container && countEl) {
                countEl.textContent = `(${container.children.length})`;
            }
        });
    }

    function addTaskToColumn(task, status) {
        const container = document.getElementById(`tasks-${status}`);
        if (!container) return;

        const card = document.createElement('div');
        card.className = `kanban-card ${status}`;
        card.id = `task-card-${task.id}`;
        card.innerHTML = `
            <h4>${task.title}</h4>
            <p>${task.description || ''}</p>
            <div style="font-size:0.7rem;margin-top:8px;opacity:0.6;font-family:monospace;">${task.file_path || ''}</div>
        `;
        container.appendChild(card);
    }

    function initBacklog(tasks) {
        const board = document.getElementById('kanban-board');
        if (board) board.style.display = 'flex';

        ['todo', 'in_progress', 'done'].forEach(status => {
            const el = document.getElementById(`tasks-${status}`);
            if (el) el.innerHTML = '';
        });

        tasks.forEach(task => addTaskToColumn(task, task.status || 'todo'));
        updateCounters();
    }

    function moveTask(taskId, newStatus) {
        const card = document.getElementById(`task-card-${taskId}`);
        const dest = document.getElementById(`tasks-${newStatus}`);
        if (!card || !dest) return;

        card.classList.remove('todo', 'in_progress', 'done');
        card.classList.add(newStatus);
        dest.appendChild(card);
        updateCounters();
    }

    return { initBacklog, moveTask };
}());
