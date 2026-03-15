"""
E2E SPA tests — sidebar navigation (requires uvicorn mock server).

Tests: nav items exist, clicking changes active view, group collapse, active class.
All API calls that could touch Ollama are not invoked by these navigation actions.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_default_view_loads_without_js_errors(page, base_url):
    """The home page loads without any JavaScript page errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(base_url)
    # Use 'load' (not networkidle — SSE connections keep the network busy indefinitely)
    page.wait_for_load_state("load", timeout=15_000)
    assert not errors, f"JavaScript errors on page load: {errors}"


@pytest.mark.e2e
def test_sidebar_nav_items_exist(page, base_url):
    """At least 5 .nav-item elements are rendered in the sidebar."""
    page.goto(base_url)
    count = page.locator(".nav-item").count()
    assert count >= 5, f"Expected >= 5 nav items, found {count}"


@pytest.mark.e2e
def test_clicking_nav_item_shows_target_view(page, base_url):
    """Clicking a .nav-item[data-view] makes that view visible."""
    page.goto(base_url)

    nav_item = page.locator(".nav-item[data-view]").first
    view_name = nav_item.get_attribute("data-view")
    assert view_name, "First .nav-item[data-view] must have a non-empty data-view attribute"

    nav_item.click()

    view_selector = f"#{view_name}-view, [data-view-id='{view_name}'], #{view_name}"
    view = page.locator(view_selector).first
    expect(view).to_be_visible(timeout=5_000)


@pytest.mark.e2e
def test_active_nav_item_gets_active_class(page, base_url):
    """Clicking a nav item gives it the 'active' CSS class."""
    page.goto(base_url)
    nav_item = page.locator(".nav-item[data-view]").first
    nav_item.click()
    # Use re.compile — to_have_class with a plain string does exact match, not regex
    expect(nav_item).to_have_class(re.compile(r"active"), timeout=3_000)


@pytest.mark.e2e
def test_nav_group_header_toggles_children(page, base_url):
    """Clicking a .nav-group-header toggles its aria-expanded attribute.

    NOTE: In collapsed 64px icon-rail mode the sidebar suppresses nav-group
    header pointer-events and forces all group contents open.  The sidebar must
    be expanded to 240px mode before this interaction test runs.
    """
    page.goto(base_url)

    # Expand sidebar to full mode so group headers are interactive.
    # The collapse toggle is display:none in icon-rail mode — use logo btn instead.
    sidebar = page.locator(".sidebar")
    if not sidebar.evaluate("el => el.classList.contains('sidebar--expanded')"):
        toggle = page.locator("#sidebar-collapse-toggle")
        (toggle if toggle.is_visible() else page.locator("#sidebar-logo-btn")).click()
        page.wait_for_timeout(300)

    headers = page.locator(".nav-group-header[aria-expanded]")
    if headers.count() == 0:
        pytest.skip("No .nav-group-header with aria-expanded found in current layout")

    header = headers.first
    before = header.get_attribute("aria-expanded")
    assert before in ("true", "false"), f"Unexpected aria-expanded='{before}'"

    header.click()
    page.wait_for_timeout(400)

    after = header.get_attribute("aria-expanded")
    expected = "true" if before == "false" else "false"
    assert after == expected, f"Expected aria-expanded to toggle from '{before}' to '{expected}', got '{after}'"
