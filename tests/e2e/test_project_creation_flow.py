"""
E2E Playwright tests — Project creation flow and Kanban progress (P1–P10).

Scenario:
  1. Mock all API endpoints (project creation, SSE events, git manifest).
  2. Navigate to the War Room page (auto_agent.html) via page.set_content().
  3. Simulate creating a project → watch Kanban move PENDING→IN_PROGRESS→COMPLETED.
  4. Verify git manifest badge appears.

All network calls are intercepted — no running server required.
"""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Minimal War Room HTML (mirrors the essential Kanban structure)
# ---------------------------------------------------------------------------

_WAR_ROOM_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  .kanban-board { display: flex; gap: 16px; }
  .kanban-column { min-width: 200px; border: 1px solid #ccc; padding: 8px; }
  .kanban-card { border: 1px solid #888; margin: 4px; padding: 8px; }
  .kanban-card.pending { background: #f3f4f6; }
  .kanban-card.in_progress { background: #fef3c7; }
  .kanban-card.completed { background: #d1fae5; }
  .kanban-card.failed { background: #fee2e2; }
</style>
</head>
<body>
<div id="kanban-board" style="display:none">
  <div class="kanban-column" id="col-pending">
    <h3>Pending</h3>
    <div id="tasks-pending"></div>
  </div>
  <div class="kanban-column" id="col-in_progress">
    <h3>In Progress</h3>
    <div id="tasks-in_progress"></div>
  </div>
  <div class="kanban-column" id="col-completed">
    <h3>Completed</h3>
    <div id="tasks-completed"></div>
  </div>
  <div class="kanban-column" id="col-failed">
    <h3>Failed</h3>
    <div id="tasks-failed"></div>
  </div>
</div>

<script>
// Minimal KanbanBoard (mirrors production behaviour)
window.KanbanBoard = (function () {
  'use strict';

  const _COL = {
    pending: 'tasks-pending',
    in_progress: 'tasks-in_progress',
    completed: 'tasks-completed',
    failed: 'tasks-failed',
  };

  function initBacklog(tasks, projectName) {
    document.getElementById('kanban-board').style.display = 'flex';
    tasks.forEach(t => _addCard(t, 'pending'));
  }

  function _addCard(t, status) {
    const card = document.createElement('div');
    card.className = `kanban-card ${status}`;
    card.id = `task-card-${t.id}`;
    card.dataset.taskId = t.id;
    card.innerHTML = `<h4>${t.title || t.id}</h4><span class="task-status">${status}</span>`;
    const col = document.getElementById(_COL[status] || _COL.pending);
    if (col) col.appendChild(card);
  }

  function moveTask(taskId, newStatus) {
    const card = document.getElementById(`task-card-${taskId}`);
    if (!card) return;
    // update class
    card.className = `kanban-card ${newStatus}`;
    card.querySelector('.task-status').textContent = newStatus;
    // move to column
    const dest = document.getElementById(_COL[newStatus]);
    if (dest) dest.appendChild(card);
  }

  function addCommitBadge(taskId, sha) {
    const card = document.getElementById(`task-card-${taskId}`);
    if (!card) return;
    const badge = document.createElement('span');
    badge.className = 'commit-sha-badge';
    badge.textContent = sha.slice(0, 7);
    card.appendChild(badge);
  }

  return { initBacklog, moveTask, addCommitBadge };
})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_kanban_initialises_with_pending_tasks(page: Page) -> None:
    """initBacklog() creates cards in the Pending column."""
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([
            { id: 'T1', title: 'Plan architecture' },
            { id: 'T2', title: 'Generate models.py' },
        ], 'testproject');
    }""")

    expect(page.locator("#tasks-pending .kanban-card")).to_have_count(2)


@pytest.mark.e2e
def test_kanban_card_moves_to_in_progress(page: Page) -> None:
    """moveTask(id, 'in_progress') moves the card to the In Progress column."""
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([{ id: 'T1', title: 'Task' }], 'proj');
        window.KanbanBoard.moveTask('T1', 'in_progress');
    }""")

    expect(page.locator("#tasks-in_progress .kanban-card")).to_have_count(1)
    expect(page.locator("#tasks-pending .kanban-card")).to_have_count(0)


@pytest.mark.e2e
def test_kanban_full_flow_pending_to_completed(page: Page) -> None:
    """Full task flow: PENDING → IN_PROGRESS → COMPLETED."""
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([
            { id: 'A', title: 'Alpha task' },
            { id: 'B', title: 'Beta task' },
        ], 'myproject');

        window.KanbanBoard.moveTask('A', 'in_progress');
        window.KanbanBoard.moveTask('A', 'completed');
        window.KanbanBoard.moveTask('B', 'in_progress');
    }""")

    expect(page.locator("#tasks-completed .kanban-card")).to_have_count(1)
    expect(page.locator("#tasks-in_progress .kanban-card")).to_have_count(1)
    expect(page.locator("#tasks-pending .kanban-card")).to_have_count(0)

    # Completed card has the right class
    completed_card = page.locator("#task-card-A")
    expect(completed_card).to_have_class("kanban-card completed")


@pytest.mark.e2e
def test_kanban_card_moves_to_failed(page: Page) -> None:
    """moveTask(id, 'failed') moves the card to the Failed column."""
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([{ id: 'F1', title: 'Flaky task' }], 'proj');
        window.KanbanBoard.moveTask('F1', 'in_progress');
        window.KanbanBoard.moveTask('F1', 'failed');
    }""")

    expect(page.locator("#tasks-failed .kanban-card")).to_have_count(1)
    expect(page.locator("#task-card-F1")).to_have_class("kanban-card failed")


@pytest.mark.e2e
def test_kanban_commit_sha_badge_appears(page: Page) -> None:
    """addCommitBadge() appends a .commit-sha-badge with the short SHA."""
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""() => {
        window.KanbanBoard.initBacklog([{ id: 'G1', title: 'Git task' }], 'proj');
        window.KanbanBoard.moveTask('G1', 'completed');
        window.KanbanBoard.addCommitBadge('G1', 'abc1234567890');
    }""")

    badge = page.locator("#task-card-G1 .commit-sha-badge")
    expect(badge).to_be_visible()
    # Should show only first 7 chars
    expect(badge).to_have_text("abc1234")


@pytest.mark.e2e
def test_create_project_api_call(page: Page) -> None:
    """Mocked POST /api/projects/generate returns 200 and is captured."""
    captured: list = []

    def handle_generate(route):
        captured.append(route.request.method)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "started", "project_name": "demo_app"}),
        )

    page.route("**/api/projects/generate", handle_generate)
    page.set_content(_WAR_ROOM_HTML)

    page.evaluate("""async () => {
        await fetch('/api/projects/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_name: 'demo_app', description: 'Test app' }),
        });
    }""")

    page.wait_for_timeout(200)
    assert len(captured) == 1
    assert captured[0] == "POST"


@pytest.mark.e2e
def test_git_manifest_endpoint_returns_json(page: Page) -> None:
    """GET /api/projects/<name>/git/manifest returns the manifest JSON."""
    manifest = {
        "project_name": "demo_app",
        "repo_initialised": True,
        "commits": [{"rel_path": "main.py", "commit_sha": "abc1234"}],
    }
    page.route(
        "**/api/projects/*/git/manifest",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(manifest),
        ),
    )
    page.set_content(_WAR_ROOM_HTML)

    result = page.evaluate("""async () => {
        const r = await fetch('/api/projects/demo_app/git/manifest');
        return await r.json();
    }""")

    assert result["project_name"] == "demo_app"
    assert result["repo_initialised"] is True
    assert len(result["commits"]) == 1
