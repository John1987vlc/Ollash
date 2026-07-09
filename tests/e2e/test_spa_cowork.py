"""
E2E tests for CoWork tab — navigation, UI elements, and minimal sidebar refactor.

Requires a running Ollash server (uvicorn on localhost:5000) and Playwright.
Run with:  pytest tests/e2e/test_spa_cowork.py -m e2e
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_cowork_nav_item_exists(page, base_url):
    """CoWork nav item is present in the sidebar."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    cowork_btn = page.locator(".nav-item[data-view='cowork']")
    expect(cowork_btn).to_be_visible()


@pytest.mark.e2e
def test_cowork_view_loads_on_click(page, base_url):
    """Clicking CoWork nav item makes the cowork view visible."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    page.locator(".nav-item[data-view='cowork']").click()
    view = page.locator("#cowork-view")
    expect(view).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_nav_item_gets_active_class(page, base_url):
    """Clicking CoWork nav item applies the 'active' CSS class."""
    import re

    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    btn = page.locator(".nav-item[data-view='cowork']")
    btn.click()
    expect(btn).to_have_class(re.compile(r"active"), timeout=3_000)


# ---------------------------------------------------------------------------
# CoWork UI elements
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_cowork_has_path_input(page, base_url):
    """CoWork view contains a workspace path text input."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    path_input = page.locator("#cowork-path-input")
    expect(path_input).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_has_assign_button(page, base_url):
    """CoWork view has an 'Asignar' button."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    assign_btn = page.locator("#cowork-assign-btn")
    expect(assign_btn).to_be_visible(timeout=5_000)
    expect(assign_btn).to_contain_text("Asignar")


@pytest.mark.e2e
def test_cowork_has_chat_input(page, base_url):
    """CoWork view has a chat textarea for sending messages."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    chat_input = page.locator("#cowork-input")
    expect(chat_input).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_has_send_button(page, base_url):
    """CoWork view has a send button."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    send_btn = page.locator("#cowork-send-btn")
    expect(send_btn).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_has_welcome_screen(page, base_url):
    """CoWork view shows a welcome screen with example prompts."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    welcome = page.locator("#cowork-welcome-screen")
    expect(welcome).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_send_disabled_without_workspace(page, base_url):
    """Send button is initially disabled until a workspace is assigned."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    page.wait_for_timeout(500)
    send_btn = page.locator("#cowork-send-btn")
    expect(send_btn).to_be_disabled(timeout=3_000)


@pytest.mark.e2e
def test_cowork_has_file_browser_panel(page, base_url):
    """CoWork view has a left-panel file browser."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    browser = page.locator("#cowork-file-browser")
    expect(browser).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_cowork_new_button_exists(page, base_url):
    """CoWork view has a 'Nuevo' button to start a new conversation."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    new_btn = page.locator("#cowork-new-btn")
    expect(new_btn).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# Minimal sidebar refactor
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_sidebar_has_minimal_nav_items(page, base_url):
    """Sidebar contains exactly the 5 required nav items after refactor."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)

    for view in ("chat", "cowork", "projects", "benchmark", "settings"):
        btn = page.locator(f".nav-item[data-view='{view}']")
        expect(btn).to_be_visible(timeout=3_000), f"Expected nav item data-view='{view}' to be visible"


@pytest.mark.e2e
def test_sidebar_removed_items_not_visible(page, base_url):
    """Removed nav items (knowledge, security, help) are not visible."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)

    for removed_view in ("knowledge", "security", "help"):
        btn = page.locator(f".nav-item[data-view='{removed_view}']")
        expect(btn).not_to_be_visible(timeout=2_000), f"Expected removed nav item '{removed_view}' NOT to be visible"


@pytest.mark.e2e
def test_sidebar_insights_label(page, base_url):
    """The benchmark nav item is labelled 'Insights' after refactor."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    insights_btn = page.locator(".nav-item[data-view='benchmark']")
    expect(insights_btn).to_contain_text("Insights")


# ---------------------------------------------------------------------------
# JavaScript errors
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_cowork_no_js_errors_on_load(page, base_url):
    """CoWork view loads without any JavaScript page errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    page.locator(".nav-item[data-view='cowork']").click()
    page.wait_for_timeout(1_000)

    assert not errors, f"JavaScript errors in CoWork view: {errors}"


@pytest.mark.e2e
def test_cowork_path_input_accepts_text(page, base_url):
    """The workspace path input accepts typed text."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='cowork']").click()
    path_input = page.locator("#cowork-path-input")
    path_input.fill("/tmp/test_workspace")
    expect(path_input).to_have_value("/tmp/test_workspace")
