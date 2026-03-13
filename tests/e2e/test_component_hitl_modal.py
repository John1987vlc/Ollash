"""
E2E Playwright tests — HITLModal component (component-isolated).

Injects hitl-modal.js into a minimal HTML page via set_content().
No server or Ollama instance required. API calls are intercepted via page.route().

HITLModal API:
  - HITLModal.show(taskId, agentId, question) — removes 'hidden' from #hitl-modal-overlay
  - HITLModal.hide()                           — sets 'hidden' on #hitl-modal-overlay
  Buttons:
  - #hitl-submit-btn → POST /api/hil/respond  {request_id, response: "approve", feedback}
  - #hitl-reject-btn → POST /api/hil/respond  {request_id, response: "reject",  feedback}
  - click overlay backdrop → hide()
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_JS_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/hitl-modal.js"

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body>
  <!-- Minimal HITL modal markup matching what hitl-modal.js expects -->
  <div id="hitl-modal-overlay" hidden
       role="dialog" aria-modal="true" aria-labelledby="hitl-modal-title">
    <div id="hitl-modal-card">
      <h2 id="hitl-modal-title">Human Input Required</h2>
      <p id="hitl-modal-agent"></p>
      <p id="hitl-modal-question"></p>
      <p id="hitl-task-id-display"></p>
      <textarea id="hitl-answer-input"></textarea>
      <button id="hitl-submit-btn">Approve</button>
      <button id="hitl-reject-btn">Reject</button>
    </div>
  </div>
  <script>{js_src}</script>
</body>
</html>"""


def _html() -> str:
    js_src = _JS_PATH.read_text(encoding="utf-8")
    return _HTML_TEMPLATE.format(js_src=js_src)


@pytest.mark.e2e
def test_modal_hidden_by_default(page_isolated: Page) -> None:
    """#hitl-modal-overlay starts with the hidden attribute."""
    page_isolated.set_content(_html())
    overlay = page_isolated.locator("#hitl-modal-overlay")
    expect(overlay).to_be_hidden()


@pytest.mark.e2e
def test_show_makes_modal_visible(page_isolated: Page) -> None:
    """HITLModal.show() removes the hidden attribute and shows the overlay."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => window.HITLModal.show('task-42', 'developer_0', 'Confirm deployment?')")
    expect(page_isolated.locator("#hitl-modal-overlay")).to_be_visible()
    expect(page_isolated.locator("#hitl-modal-question")).to_have_text("Confirm deployment?")
    expect(page_isolated.locator("#hitl-task-id-display")).to_have_text("task-42")


@pytest.mark.e2e
def test_approve_button_posts_response(page_isolated: Page) -> None:
    """Clicking #hitl-submit-btn POSTs to /api/hil/respond with response='approve'."""
    page_isolated.set_content(_html())

    posted: list[dict] = []

    def _handle(route):
        body = json.loads(route.request.post_data or "{}")
        posted.append(body)
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True}))

    page_isolated.route("**/api/hil/respond", _handle)

    # Patch fetch so relative /api/* URLs resolve to http://localhost (set_content base is about:blank)
    page_isolated.evaluate("""() => {
        const orig = window.fetch;
        window.fetch = (url, opts) => url.startsWith('/') ? orig('http://localhost' + url, opts) : orig(url, opts);
    }""")

    page_isolated.evaluate("() => window.HITLModal.show('t1', 'agent', 'OK?')")
    page_isolated.locator("#hitl-submit-btn").click()

    expect(page_isolated.locator("#hitl-modal-overlay")).to_be_hidden()
    assert len(posted) == 1, "Expected exactly one POST to /api/hil/respond"
    assert posted[0].get("response") == "approve"
    assert posted[0].get("request_id") == "t1"


@pytest.mark.e2e
def test_reject_button_posts_response(page_isolated: Page) -> None:
    """Clicking #hitl-reject-btn POSTs to /api/hil/respond with response='reject'."""
    page_isolated.set_content(_html())

    posted: list[dict] = []

    def _handle(route):
        body = json.loads(route.request.post_data or "{}")
        posted.append(body)
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True}))

    page_isolated.route("**/api/hil/respond", _handle)

    # Patch fetch so relative /api/* URLs resolve to http://localhost (set_content base is about:blank)
    page_isolated.evaluate("""() => {
        const orig = window.fetch;
        window.fetch = (url, opts) => url.startsWith('/') ? orig('http://localhost' + url, opts) : orig(url, opts);
    }""")

    page_isolated.evaluate("() => window.HITLModal.show('t2', 'agent', 'Reject me?')")
    page_isolated.locator("#hitl-reject-btn").click()

    assert len(posted) == 1
    assert posted[0].get("response") == "reject"


@pytest.mark.e2e
def test_hide_closes_modal(page_isolated: Page) -> None:
    """HITLModal.hide() re-adds the hidden attribute."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => window.HITLModal.show('t3', 'agent', 'Question?')")
    expect(page_isolated.locator("#hitl-modal-overlay")).to_be_visible()
    page_isolated.evaluate("() => window.HITLModal.hide()")
    expect(page_isolated.locator("#hitl-modal-overlay")).to_be_hidden()
