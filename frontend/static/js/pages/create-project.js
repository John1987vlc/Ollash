/**
 * Create Project Wizard - Kanban Board
 * Manages task board displayed during project generation.
 * Extracted from create_project.html inline script.
 */
window.KanbanBoard = (function () {
    function updateCounters() {
        ['todo', 'in_progress', 'done'].forEach(s => {
            const container = document.getElementById(`tasks-${s}`);
            const countEl = document.getElementById(`count-${s}`);
            if (container && countEl) {
                countEl.textContent = `(${container.children.length})`;
            }
        });
    }

    function initBacklog(tasks) {
        const board = document.getElementById('kanban-board');
        if (board) board.style.display = 'flex';

        ['todo', 'in_progress', 'done'].forEach(s => {
            const el = document.getElementById(`tasks-${s}`);
            if (el) el.innerHTML = '';
        });

        tasks.forEach(t => {
            const card = document.createElement('div');
            card.className = 'kanban-card todo';
            card.id = `task-card-${t.id}`;
            card.innerHTML = `<h4>${t.title}</h4><p>${t.description || ''}</p>`;
            document.getElementById('tasks-todo')?.appendChild(card);
        });

        updateCounters();
    }

    function moveTask(id, status) {
        const card = document.getElementById(`task-card-${id}`);
        const dest = document.getElementById(`tasks-${status}`);
        if (card && dest) {
            card.className = `kanban-card ${status}`;
            dest.appendChild(card);
            updateCounters();
        }
    }

    return { initBacklog, moveTask };
}());
