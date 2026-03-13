"""
E2E Playwright tests — ConfirmDialog component (component-isolated).

Injects confirm-dialog.js into a minimal HTML page via set_content().
No server or Ollama instance required.

ConfirmDialog API:
  - ConfirmDialog.ask(message) → Promise<boolean>  — shows #confirm-modal
  - ConfirmDialog.close()                           — hides modal, resolves false
  Buttons:
  - #confirm-modal-ok     → resolves true
  - #confirm-modal-cancel → resolves false
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_JS_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/confirm-dialog.js"

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body>
  <!-- Minimal modal markup matching what confirm-dialog.js expects -->
  <div id="confirm-modal" role="dialog" aria-modal="true"
       style="display:none; position:fixed; inset:0; background:rgba(0,0,0,.5);">
    <div>
      <p id="confirm-modal-message"></p>
      <button id="confirm-modal-ok">OK</button>
      <button id="confirm-modal-cancel">Cancel</button>
    </div>
  </div>
  <script>{js_src}</script>
  <script>
    // Track callback invocations for assertions
    window._callbackResult = null;
  </script>
</body>
</html>"""


def _html() -> str:
    js_src = _JS_PATH.read_text(encoding="utf-8")
    return _HTML_TEMPLATE.format(js_src=js_src)


@pytest.mark.e2e
def test_dialog_hidden_by_default(page_isolated: Page) -> None:
    """#confirm-modal starts with display:none (hidden)."""
    page_isolated.set_content(_html())
    modal = page_isolated.locator("#confirm-modal")
    expect(modal).to_be_hidden()


@pytest.mark.e2e
def test_ask_shows_modal_with_message(page_isolated: Page) -> None:
    """ConfirmDialog.ask() makes the modal visible and sets the message text."""
    page_isolated.set_content(_html())
    # Don't await — just kick it off so modal appears
    page_isolated.evaluate("() => { window.ConfirmDialog.ask('Delete the project?'); }")
    expect(page_isolated.locator("#confirm-modal")).to_be_visible()
    expect(page_isolated.locator("#confirm-modal-message")).to_have_text("Delete the project?")


@pytest.mark.e2e
def test_ok_button_resolves_true(page_isolated: Page) -> None:
    """Clicking #confirm-modal-ok resolves the promise with true and hides the modal."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.ConfirmDialog.ask('Confirm?').then(r => { window._callbackResult = r; });
    }""")
    expect(page_isolated.locator("#confirm-modal")).to_be_visible()
    page_isolated.locator("#confirm-modal-ok").click()
    expect(page_isolated.locator("#confirm-modal")).to_be_hidden()
    result = page_isolated.evaluate("() => window._callbackResult")
    assert result is True, f"Expected true but got {result}"


@pytest.mark.e2e
def test_cancel_button_resolves_false(page_isolated: Page) -> None:
    """Clicking #confirm-modal-cancel resolves the promise with false and hides the modal."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.ConfirmDialog.ask('Delete?').then(r => { window._callbackResult = r; });
    }""")
    page_isolated.locator("#confirm-modal-cancel").click()
    expect(page_isolated.locator("#confirm-modal")).to_be_hidden()
    result = page_isolated.evaluate("() => window._callbackResult")
    assert result is False, f"Expected false but got {result}"


@pytest.mark.e2e
def test_close_hides_modal(page_isolated: Page) -> None:
    """ConfirmDialog.close() hides the modal without needing a button click."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => { window.ConfirmDialog.ask('Close me.'); }")
    expect(page_isolated.locator("#confirm-modal")).to_be_visible()
    page_isolated.evaluate("() => window.ConfirmDialog.close()")
    expect(page_isolated.locator("#confirm-modal")).to_be_hidden()
