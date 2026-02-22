"""
E2E Error Handling & Feedback Tests for Ollash UI.

Verifies:
- SSE reconnect banner appears when the alerts stream disconnects.
- Run button in sandbox is disabled during code execution.
- Confirmation modal appears instead of native confirm() for destructive actions.
"""
import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# SSE Reconnect Banner
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_sse_reconnect_banner_appears_on_disconnect(page, base_url):
    """
    Al simular un error en el SSE handler, debe aparecer el banner de reconexión.
    """
    page.goto(base_url)

    # Wait for alert handler to initialize
    page.wait_for_function("typeof window.proactiveAlertHandler !== 'undefined'", timeout=5000)

    # Simulate an SSE error by calling handleSSEError directly
    page.evaluate("window.proactiveAlertHandler.handleSSEError()")

    # Banner should appear
    banner = page.locator("#sse-reconnect-banner")
    expect(banner).to_be_visible(timeout=3000)

    banner_text = banner.inner_text()
    assert len(banner_text.strip()) > 0, "Reconnect banner should have descriptive text"


@pytest.mark.e2e
def test_sse_reconnect_banner_has_alert_role(page, base_url):
    """
    El banner de reconexión debe tener role='alert' para screen readers.
    """
    page.goto(base_url)
    page.wait_for_function("typeof window.proactiveAlertHandler !== 'undefined'", timeout=5000)
    page.evaluate("window.proactiveAlertHandler.handleSSEError()")

    banner = page.locator("#sse-reconnect-banner")
    expect(banner).to_be_visible(timeout=3000)

    role = banner.get_attribute("role")
    assert role == "alert", f"Banner must have role='alert', got '{role}'"


@pytest.mark.e2e
def test_sse_reconnect_banner_hides_on_reconnect(page, base_url):
    """
    Al simular una reconexión exitosa, el banner debe desaparecer.
    """
    page.goto(base_url)
    page.wait_for_function("typeof window.proactiveAlertHandler !== 'undefined'", timeout=5000)

    # Disconnect
    page.evaluate("window.proactiveAlertHandler.handleSSEError()")
    page.locator("#sse-reconnect-banner").wait_for(state="visible", timeout=3000)

    # Reconnect (simulate open event)
    page.evaluate("""
        () => {
            window.proactiveAlertHandler.isConnected = true;
            window.proactiveAlertHandler.reconnectAttempts = 0;
            window.proactiveAlertHandler._hideReconnectBanner();
        }
    """)

    # Banner should fade out within 2.5s (plus buffer)
    page.wait_for_timeout(3000)
    banner_exists = page.evaluate("document.getElementById('sse-reconnect-banner') !== null")
    assert not banner_exists, "Reconnect banner should be removed after successful reconnection"


# ---------------------------------------------------------------------------
# Sandbox Run Button – loading state
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_sandbox_run_button_exists(page, base_url):
    """
    El botón Run del sandbox debe existir en la página /sandbox.
    """
    page.goto(f"{base_url}/sandbox")
    run_btn = page.locator("#run-sandbox-btn")
    expect(run_btn).to_be_visible(timeout=5000)


@pytest.mark.e2e
def test_sandbox_run_button_disabled_during_execution(page, base_url):
    """
    El botón Run debe quedar disabled durante la ejecución de código.
    """
    page.goto(f"{base_url}/sandbox")
    page.wait_for_selector("#run-sandbox-btn", timeout=5000)

    # Intercept the fetch call to control timing
    page.route("**/sandbox/execute", lambda route: (
        page.wait_for_timeout(500),
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"status": "success", "output": "Hello!", "duration": 0.1}',
        )
    ))

    run_btn = page.locator("#run-sandbox-btn")
    
    # Inject mock editor if real one didn't load (common in CI/E2E without CDN access)
    page.evaluate("""
        if (typeof window.monacoEditorInstance === 'undefined') {
            window.monacoEditorInstance = { getValue: () => 'print("test")' };
            // Also need to set the local variable 'editor' if possible, 
            // but since it's in a closure, we might need to rely on our fallback in sandbox.js
        }
    """)
    
    run_btn.click()

    # Check disabled state immediately after click
    is_disabled = run_btn.is_disabled()
    
    # Cleanup routes to prevent TargetClosedError in subsequent tests
    page.unroute("**/sandbox/execute")
    
    assert is_disabled, "Run button should be disabled during code execution"


# ---------------------------------------------------------------------------
# Confirmation Modal – replaces native confirm()
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_confirm_modal_shows_on_clear_chat(page, base_url):
    """
    Al intentar limpiar el chat, debe aparecer el modal de confirmación
    en lugar del confirm() nativo del navegador.
    """
    page.goto(base_url)

    # Ensure we're on the chat view
    chat_view = page.locator("#chat-view")
    if not chat_view.is_visible():
        # Navigate to chat
        page.locator(".nav-item[data-view='chat']").first.click()

    clear_btn = page.locator("#clear-chat-btn")
    if not clear_btn.is_visible():
        pytest.skip("Clear chat button not visible in current view")

    # Listen for native dialog – it should NOT appear
    dialog_appeared = {"value": False}
    page.on("dialog", lambda d: (dialog_appeared.__setitem__("value", True), d.dismiss()))

    clear_btn.click()

    # The custom confirm modal should appear instead of native dialog
    confirm_modal = page.locator("#confirm-modal")
    expect(confirm_modal).to_be_visible(timeout=2000)
    assert not dialog_appeared["value"], "Native confirm() should NOT have been used; use modal instead"


@pytest.mark.e2e
def test_confirm_modal_cancel_does_not_clear_chat(page, base_url):
    """
    Al cancelar el modal de confirmación, el historial del chat debe permanecer.
    """
    page.goto(base_url)

    # Send a message first (just inject text into DOM)
    page.evaluate("""
        document.getElementById('chat-messages').innerHTML +=
            '<div class="chat-message user">Test message</div>';
    """)

    clear_btn = page.locator("#clear-chat-btn")
    if not clear_btn.is_visible():
        pytest.skip("Clear chat button not visible")

    clear_btn.click()

    confirm_modal = page.locator("#confirm-modal")
    expect(confirm_modal).to_be_visible(timeout=2000)

    # Click Cancel
    page.locator("#confirm-modal-cancel").click()

    # Modal should close
    expect(confirm_modal).not_to_be_visible()

    # Chat should still have content
    messages = page.locator("#chat-messages").inner_text()
    assert "Test message" in messages, "Chat history should NOT be cleared when confirmation is cancelled"


@pytest.mark.e2e
def test_confirm_modal_ok_clears_chat(page, base_url):
    """
    Al confirmar, el chat debe limpiarse.
    """
    page.goto(base_url)

    page.evaluate("""
        document.getElementById('chat-messages').innerHTML +=
            '<div class="chat-message user">Content to clear</div>';
    """)

    clear_btn = page.locator("#clear-chat-btn")
    if not clear_btn.is_visible():
        pytest.skip("Clear chat button not visible")

    clear_btn.click()

    confirm_modal = page.locator("#confirm-modal")
    expect(confirm_modal).to_be_visible(timeout=2000)

    # Click Confirm
    page.locator("#confirm-modal-ok").click()

    # Modal should close
    expect(confirm_modal).not_to_be_visible()

    # Chat messages should be reset (welcome message present, test content gone)
    messages = page.locator("#chat-messages").inner_text()
    assert "Content to clear" not in messages, "Chat content should be cleared after confirmation"
