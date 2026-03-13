"""
E2E SPA tests — chat interface (requires uvicorn mock server).

All /api/chat calls are mocked so no Ollama instance is needed.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect


def _mock_chat_api(page):
    """Intercept POST /api/chat and return a canned JSON response."""

    def _handler(route):
        if route.request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"status": "started", "session_id": "test-session-1"}),
            )
        else:
            route.continue_()

    page.route("**/api/chat**", _handler)


def _navigate_to_chat(page, base_url):
    """Navigate to the home page and click the Chat nav item."""
    page.goto(base_url)
    chat_nav = page.locator(".nav-item[data-view='chat']")
    if chat_nav.count() == 0:
        pytest.skip("No .nav-item[data-view='chat'] found — chat not in sidebar")
    chat_nav.click()
    expect(page.locator("#chat-view")).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_chat_input_clears_after_send(page, base_url):
    """Typing a message and clicking Send clears the input field."""
    _mock_chat_api(page)
    _navigate_to_chat(page, base_url)

    chat_input = page.locator("#chat-input")
    send_btn = page.locator("#send-btn")

    chat_input.fill("Hello, agent!")
    send_btn.click()

    expect(chat_input).to_have_value("", timeout=5_000)


@pytest.mark.e2e
def test_sent_message_appears_in_chat(page, base_url):
    """Sent message text appears in the #chat-messages container."""
    _mock_chat_api(page)
    _navigate_to_chat(page, base_url)

    test_msg = "Test message from E2E"
    page.locator("#chat-input").fill(test_msg)
    page.locator("#send-btn").click()

    expect(page.locator("#chat-messages")).to_contain_text(test_msg, timeout=5_000)


@pytest.mark.e2e
def test_agent_card_gets_active_class(page, base_url):
    """Clicking an agent card (.btn-card) gives it the 'active' CSS class."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='chat']").click() if page.locator(
        ".nav-item[data-view='chat']"
    ).count() else None

    cards = page.locator(".btn-card")
    if cards.count() == 0:
        pytest.skip("No .btn-card agent cards found in chat view")

    cards.first.click()
    expect(cards.first).to_have_class(".*active.*", timeout=3_000)


@pytest.mark.e2e
def test_clear_chat_shows_confirmation_modal(page, base_url):
    """Clicking 'Clear Chat' opens #confirm-modal instead of native browser confirm()."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='chat']").click() if page.locator(
        ".nav-item[data-view='chat']"
    ).count() else None

    clear_btn = page.locator("#clear-chat-btn")
    if not clear_btn.is_visible():
        pytest.skip("Clear chat button not found or not visible")

    native_seen = {"value": False}
    page.on("dialog", lambda d: (native_seen.__setitem__("value", True), d.dismiss()))

    clear_btn.click()

    expect(page.locator("#confirm-modal")).to_be_visible(timeout=3_000)
    assert not native_seen["value"], (
        "Native window.confirm() must NOT be used — custom modal should appear"
    )

    # Dismiss via Cancel so state is clean
    page.locator("#confirm-modal-cancel").click()
    expect(page.locator("#confirm-modal")).to_be_hidden()
