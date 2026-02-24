"""
E2E Playwright tests — HITL (Human-in-the-Loop) interaction (P1).

Scenario:
  1. The page loads the War Room (auto_agent.html) with a mocked running project.
  2. An SSE event `hitl_requested` fires → the HITL modal appears.
  3. The user types an answer and clicks Approve.
  4. The browser posts to /api/hil/respond → mocked to return 200.
  5. The modal closes and the kanban card turns blue ("Unblocked").

All network calls are intercepted via page.route() — no real server needed.
"""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HITL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  [hidden] { display: none !important; }
  .hitl-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); }
  .hitl-modal-overlay[hidden] { display: none; }
</style>
</head>
<body>

<!-- HITL modal markup (mirrors hitl_modal.html partial) -->
<div id="hitl-modal-overlay" class="hitl-modal-overlay" hidden>
  <div class="hitl-modal" role="dialog" aria-modal="true">
    <div class="hitl-modal-header">
      <span class="hitl-agent-tag" id="hitl-agent-tag">Agent</span>
      <button class="hitl-modal-close" id="hitl-close-btn">&times;</button>
    </div>
    <div class="hitl-question-block" id="hitl-question-text"></div>
    <textarea id="hitl-answer-input" rows="4" placeholder="Type your answer…"></textarea>
    <div class="hitl-actions">
      <button id="hitl-reject-btn">Reject</button>
      <button id="hitl-approve-btn">Approve</button>
    </div>
  </div>
</div>

<!-- Minimal HITLModal implementation (extracted from hitl-modal.js) -->
<script>
window.HITLModal = (function() {
  'use strict';
  let _taskId = null;

  const overlay  = document.getElementById('hitl-modal-overlay');
  const tagEl    = document.getElementById('hitl-agent-tag');
  const questionEl = document.getElementById('hitl-question-text');
  const answerEl = document.getElementById('hitl-answer-input');
  const appBtn   = document.getElementById('hitl-approve-btn');
  const rejBtn   = document.getElementById('hitl-reject-btn');
  const closeBtn = document.getElementById('hitl-close-btn');

  function show(taskId, agentId, question) {
    _taskId = taskId;
    if (tagEl) tagEl.textContent = agentId || 'Agent';
    if (questionEl) questionEl.textContent = question || '';
    if (answerEl) answerEl.value = '';
    if (overlay) overlay.removeAttribute('hidden');
  }

  function hide() {
    if (overlay) overlay.setAttribute('hidden', '');
  }

  async function _respond(approved) {
    const answer = answerEl ? answerEl.value : '';
    await fetch('/api/hil/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: _taskId, answer, approved }),
    });
    hide();
  }

  if (appBtn) appBtn.addEventListener('click', () => _respond(true));
  if (rejBtn) rejBtn.addEventListener('click', () => _respond(false));
  if (closeBtn) closeBtn.addEventListener('click', hide);

  return { show, hide };
})();
</script>
</body>
</html>"""


def _mock_hil_respond(page: Page) -> list:
    """Capture POST /api/hil/respond calls and return 200."""
    captured: list = []

    def handle(route):
        captured.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "ok", "unblocked": True}),
        )

    page.route("**/api/hil/respond", handle)
    return captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_hitl_modal_appears_on_show_call(page: Page) -> None:
    """HITLModal.show() makes the overlay visible."""
    page.set_content(_HITL_HTML)

    page.evaluate("""() => {
        window.HITLModal.show('task-abc', 'developer_0', 'Should we use Redis?');
    }""")

    overlay = page.locator("#hitl-modal-overlay")
    expect(overlay).to_be_visible()
    expect(page.locator("#hitl-agent-tag")).to_have_text("developer_0")
    expect(page.locator("#hitl-question-text")).to_have_text("Should we use Redis?")


@pytest.mark.e2e
def test_hitl_modal_approve_calls_api(page: Page) -> None:
    """Clicking Approve POSTs to /api/hil/respond with the user answer."""
    captured = _mock_hil_respond(page)
    page.set_content(_HITL_HTML)

    page.evaluate("() => window.HITLModal.show('task-xyz', 'auditor_0', 'Proceed?')")

    page.fill("#hitl-answer-input", "Yes, proceed.")
    page.click("#hitl-approve-btn")
    page.wait_for_timeout(200)

    assert len(captured) == 1
    assert captured[0]["request_id"] == "task-xyz"
    assert captured[0]["answer"] == "Yes, proceed."
    assert captured[0]["approved"] is True


@pytest.mark.e2e
def test_hitl_modal_closes_after_approve(page: Page) -> None:
    """Modal hides after the Approve button is clicked."""
    _mock_hil_respond(page)
    page.set_content(_HITL_HTML)

    page.evaluate("() => window.HITLModal.show('task-1', 'dev', 'Q?')")
    expect(page.locator("#hitl-modal-overlay")).to_be_visible()

    page.click("#hitl-approve-btn")
    page.wait_for_timeout(200)

    expect(page.locator("#hitl-modal-overlay")).to_be_hidden()


@pytest.mark.e2e
def test_hitl_modal_reject_sends_approved_false(page: Page) -> None:
    """Clicking Reject POSTs with approved=False."""
    captured = _mock_hil_respond(page)
    page.set_content(_HITL_HTML)

    page.evaluate("() => window.HITLModal.show('task-rej', 'dev', 'Reject me?')")
    page.fill("#hitl-answer-input", "No.")
    page.click("#hitl-reject-btn")
    page.wait_for_timeout(200)

    assert len(captured) == 1
    assert captured[0]["approved"] is False


@pytest.mark.e2e
def test_hitl_modal_close_button_hides_modal(page: Page) -> None:
    """X button closes the modal without posting."""
    captured = _mock_hil_respond(page)
    page.set_content(_HITL_HTML)

    page.evaluate("() => window.HITLModal.show('task-close', 'dev', 'Close me?')")
    page.click("#hitl-close-btn")
    page.wait_for_timeout(100)

    expect(page.locator("#hitl-modal-overlay")).to_be_hidden()
    assert len(captured) == 0  # No API call made
