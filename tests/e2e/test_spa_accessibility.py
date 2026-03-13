"""
E2E SPA tests — ARIA attributes and keyboard navigation (requires uvicorn mock server).

Tests: sidebar aria-label, nav group aria-expanded, modal role='dialog',
command palette Ctrl+K / Escape, :focus-visible CSS rule.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_sidebar_nav_has_aria_label(page, base_url):
    """nav.sidebar-nav must have a non-empty aria-label attribute."""
    page.goto(base_url)
    nav = page.locator("nav.sidebar-nav")
    expect(nav).to_be_visible()
    aria_label = nav.get_attribute("aria-label")
    assert aria_label and aria_label.strip(), "Sidebar nav must have a non-empty aria-label"


@pytest.mark.e2e
def test_nav_group_headers_have_aria_expanded(page, base_url):
    """All .nav-group-header buttons must have aria-expanded='true' or 'false'."""
    page.goto(base_url)
    headers = page.locator(".nav-group-header")
    count = headers.count()
    if count == 0:
        pytest.skip("No .nav-group-header elements found in current layout")

    missing = []
    for i in range(count):
        val = headers.nth(i).get_attribute("aria-expanded")
        if val not in ("true", "false"):
            missing.append(f"header #{i}: aria-expanded='{val}'")

    assert not missing, f"nav-group-headers missing valid aria-expanded: {missing}"


@pytest.mark.e2e
def test_modals_have_dialog_role(page, base_url):
    """Every element explicitly marked as aria-modal='true' must also have role='dialog'."""
    page.goto(base_url)
    # Only check elements that declare themselves as modal overlays via aria-modal="true"
    modals = page.locator("[aria-modal='true']")
    count = modals.count()
    if count == 0:
        pytest.skip("No elements with aria-modal='true' found")

    missing = []
    for i in range(count):
        el = modals.nth(i)
        modal_id = el.get_attribute("id") or f"(index {i})"
        role = el.get_attribute("role")
        if role != "dialog":
            missing.append(f"#{modal_id}: role='{role}'")

    assert not missing, f"aria-modal='true' elements missing role='dialog': {missing}"


@pytest.mark.e2e
def test_modal_close_buttons_have_aria_label(page, base_url):
    """All .close-modal buttons must have a non-empty aria-label."""
    page.goto(base_url)
    close_btns = page.locator(".close-modal, .btn-close-ghost")
    count = close_btns.count()
    if count == 0:
        pytest.skip("No .close-modal buttons found in current layout")

    missing = []
    for i in range(count):
        label = close_btns.nth(i).get_attribute("aria-label")
        if not label or not label.strip():
            missing.append(f"close button #{i}")

    assert not missing, f"Close buttons missing aria-label: {missing}"


@pytest.mark.e2e
def test_command_palette_opens_on_ctrl_k(page, base_url):
    """Pressing Ctrl+K opens the command palette (adds 'active' class)."""
    page.goto(base_url)
    page.keyboard.press("Control+k")
    overlay = page.locator("#command-palette-overlay")
    expect(overlay).to_have_class(re.compile(r"active"), timeout=3_000)


@pytest.mark.e2e
def test_command_palette_closes_on_escape(page, base_url):
    """Pressing Escape after Ctrl+K removes the 'active' class from the palette."""
    page.goto(base_url)
    page.keyboard.press("Control+k")
    page.locator("#command-palette-overlay.active").wait_for(timeout=3_000)
    page.keyboard.press("Escape")
    expect(page.locator("#command-palette-overlay")).not_to_have_class(
        re.compile(r"active"), timeout=3_000
    )


@pytest.mark.e2e
def test_focus_visible_css_rule_exists(page, base_url):
    """The :focus-visible CSS rule must be defined in one of the loaded stylesheets."""
    page.goto(base_url)
    has_rule = page.evaluate("""() => {
        for (const sheet of document.styleSheets) {
            try {
                for (const rule of sheet.cssRules || []) {
                    if (rule.selectorText && rule.selectorText.includes(':focus-visible')) {
                        return true;
                    }
                }
            } catch (e) { /* cross-origin sheet */ }
        }
        return false;
    }""")
    assert has_rule, ":focus-visible CSS rule must be defined for keyboard accessibility"
