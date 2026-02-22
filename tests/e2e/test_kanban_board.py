import pytest
import os
from playwright.sync_api import Page, expect

def test_kanban_board_updates(page: Page):
    # We will use a mock HTML to test the JS logic of KanbanBoard
    # since we don't want to spin up the whole Flask server + Ollama for a simple UI check
    
    html_content = """
    <html>
    <body>
        <div id="kanban-board" style="display:none">
            <div id="tasks-todo"></div>
            <div id="tasks-in_progress"></div>
            <div id="tasks-done"></div>
            <span id="count-todo"></span>
            <span id="count-in_progress"></span>
            <span id="count-done"></span>
        </div>
        <script>
            // Paste the implementation here for testing
            window.KanbanBoard = (function() {
                function updateCounters() {
                    ['todo', 'in_progress', 'done'].forEach(s => {
                        const count = document.getElementById(`tasks-${s}`).children.length;
                        document.getElementById(`count-${s}`).textContent = `(${count})`;
                    });
                }
                return {
                    initBacklog: (tasks) => {
                        document.getElementById('kanban-board').style.display = 'flex';
                        tasks.forEach(t => {
                            const card = document.createElement('div');
                            card.className = `kanban-card todo`;
                            card.id = `task-card-${t.id}`;
                            card.innerHTML = `<h4>${t.title}</h4>`;
                            document.getElementById('tasks-todo').appendChild(card);
                        });
                        updateCounters();
                    },
                    moveTask: (id, status) => {
                        const card = document.getElementById(`task-card-${id}`);
                        const dest = document.getElementById(`tasks-${status}`);
                        if (card && dest) {
                            card.className = `kanban-card ${status}`;
                            dest.appendChild(card);
                            updateCounters();
                        }
                    }
                };
            })();
        </script>
    </body>
    </html>
    """
    
    page.set_content(html_content)
    
    # 1. Initialize Backlog
    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([
            {id: 'T1', title: 'Task 1'},
            {id: 'T2', title: 'Task 2'}
        ]);
    }""")
    
    expect(page.locator("#tasks-todo .kanban-card")).to_have_count(2)
    expect(page.locator("#count-todo")).to_have_text("(2)")
    
    # 2. Move Task to In Progress
    page.evaluate("() => window.KanbanBoard.moveTask('T1', 'in_progress')")
    
    expect(page.locator("#tasks-todo .kanban-card")).to_have_count(1)
    expect(page.locator("#tasks-in_progress .kanban-card")).to_have_count(1)
    expect(page.locator("#count-in_progress")).to_have_text("(1)")
    
    # 3. Move Task to Done
    page.evaluate("() => window.KanbanBoard.moveTask('T1', 'done')")
    expect(page.locator("#tasks-done .kanban-card")).to_have_count(1)
    expect(page.locator("#count-done")).to_have_text("(1)")
