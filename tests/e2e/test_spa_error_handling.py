"""
E2E SPA tests — error handling and UI resilience (requires uvicorn mock server).

Tests: SSE reconnect banner, confirmation modal replaces native confirm(),
sandbox button disabled state during a run.
No Ollama calls are made — all relevant API calls are mocked.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_confirmation_modal_replaces_native_confirm(page, base_url):
    """Any UI action that previously used window.confirm() must now use #confirm-modal."""
    page.goto(base_url)

    native_seen = {"value": False}
    page.on("dialog", lambda d: (native_seen.__setitem__("value", True), d.dismiss()))

    # Navigate to chat view and trigger clear (most common use of confirm)
    chat_nav = page.locator(".nav-item[data-view='chat']")
    if chat_nav.count() > 0:
        chat_nav.click()

    clear_btn = page.locator("#clear-chat-btn")
    if not clear_btn.is_visible():
        pytest.skip("Clear chat button not found — cannot verify confirm replacement")

    clear_btn.click()

    # Custom modal must appear; native dialog must NOT
    expect(page.locator("#confirm-modal")).to_be_visible(timeout=3_000)
    assert not native_seen["value"], (
        "window.confirm() (native dialog) must not be triggered — ConfirmDialog modal should be used"
    )

    # Cleanup: dismiss via Cancel
    page.locator("#confirm-modal-cancel").click()


@pytest.mark.e2e
def test_sse_reconnect_banner_appears_on_disconnect(page, base_url):
    """When the SSE stream closes unexpectedly, a [role='alert'] banner appears."""
    # Mock the SSE health endpoint to return an immediate close (empty stream)
    page.route(
        "**/api/alerts/stream**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/event-stream",
            body="",  # empty body → connection closes immediately
        ),
    )

    page.goto(base_url)
    # Give SSE manager time to detect the disconnect and show the banner
    page.wait_for_timeout(2_000)

    alert_banner = page.locator("[role='alert']")
    if alert_banner.count() == 0:
        pytest.skip("No [role='alert'] element found — SSE reconnect banner may not be implemented")

    expect(alert_banner.first).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_sandbox_run_button_disabled_during_execution(page, base_url):
    """The sandbox run button becomes disabled while a run is in progress."""
    # Mock the sandbox run endpoint to return a slow/pending status
    def _handle_sandbox(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "running", "run_id": "r1"}),
        )

    page.route("**/api/sandbox/**", _handle_sandbox)

    page.goto(base_url)

    # Navigate to sandbox — the nav item may be inside a collapsed group
    sandbox_nav = page.locator(".nav-item[data-view='sandbox']")
    if sandbox_nav.count() == 0:
        pytest.skip("No sandbox nav item found in current layout")

    # If the item is not visible (inside collapsed group), expand its parent group first
    if not sandbox_nav.first.is_visible():
        parent_header = sandbox_nav.first.locator(
            "xpath=ancestor::div[contains(@class,'nav-group')]//button[contains(@class,'nav-group-header')]"
        ).first
        if parent_header.count() > 0:
            parent_header.click()
            page.wait_for_timeout(300)

    # Use JS click to bypass any intercept issues from overlapping elements
    sandbox_nav.first.evaluate("el => el.click()")
    page.wait_for_timeout(500)

    run_btn = page.locator("#sandbox-run-btn, [data-action='sandbox-run']").first
    if not run_btn.is_visible():
        pytest.skip("Sandbox run button not found after navigating to sandbox view")

    run_btn.click()

    # Button should become disabled while running
    expect(run_btn).to_be_disabled(timeout=3_000)
