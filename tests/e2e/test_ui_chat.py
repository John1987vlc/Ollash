import pytest
import json
from playwright.sync_api import expect


@pytest.mark.e2e
def test_chat_ui_flow(page, base_url):
    """
    Validates the complete chat flow navigating from root.
    """

    # Mock successful session creation
    def handle_chat_api(route):
        if route.request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "started", "session_id": "test-123"}),
            )
        else:
            route.continue_()

    page.route("**/api/chat", handle_chat_api)

    # Capture all logs including errors
    page.on("console", lambda msg: print(f"BROWSER [{msg.type}]: {msg.text}"))
    page.on("pageerror", lambda exc: print(f"BROWSER ERROR: {exc}"))

    # Go to ROOT, not /chat directly
    page.goto(base_url)

    # Click on Chat nav item to ensure we are in the right view
    page.locator(".nav-item[data-view='chat']").click()

    # Wait for the view and elements
    expect(page.locator("#chat-view")).to_be_visible()

    # Wait for ChatModule to be initialized (it might take a moment after DOMContentLoaded)
    page.wait_for_function("() => typeof ChatModule !== 'undefined'")

    chat_input = page.locator("#chat-input")
    send_btn = page.locator("#send-btn")

    # Type and send
    test_message = "Test Message"
    chat_input.fill(test_message)

    print("Clicking send button...")
    send_btn.click()

    # Wait for the clear
    expect(chat_input).to_have_value("", timeout=5000)

    # Verify message appears in container
    expect(page.locator("#chat-messages")).to_contain_text(test_message)


@pytest.mark.e2e
def test_agent_cards_interactivity(page, base_url):
    """Verifies that clicking agent cards triggers a visual state change."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='chat']").click()

    expect(page.locator(".agent-card").first).to_be_visible()
    page.locator(".agent-card").first.click()

    import re

    expect(page.locator(".agent-card").first).to_have_class(re.compile(r"active"))
