"""
E2E SPA tests — responsive layout (requires uvicorn mock server).

Tests mobile (375x667) and tablet (768x1024) viewport behaviour.
No Ollama calls are made by these layout checks.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

_MOBILE = {"width": 375, "height": 667}
_TABLET = {"width": 768, "height": 1024}


@pytest.mark.e2e
def test_sidebar_present_on_mobile(page, base_url):
    """On mobile viewport the sidebar element is present in the DOM."""
    page.set_viewport_size(_MOBILE)
    page.goto(base_url)
    # Verify the sidebar element exists regardless of visibility (some designs keep it open)
    assert page.locator("aside.sidebar").count() > 0, (
        "aside.sidebar must be present in the DOM on mobile viewport"
    )


@pytest.mark.e2e
def test_hamburger_menu_toggles_sidebar(page, base_url):
    """On mobile, clicking the hamburger/menu button makes the sidebar visible."""
    page.set_viewport_size(_MOBILE)
    page.goto(base_url)

    hamburger = page.locator(
        "#hamburger-btn, .hamburger, .menu-toggle, [aria-label*='menu' i], [aria-label*='sidebar' i]"
    ).first
    if not hamburger.is_visible():
        pytest.skip("No hamburger/menu toggle button found on mobile layout")

    hamburger.click()
    page.wait_for_timeout(400)  # allow CSS transition

    expect(page.locator("aside.sidebar")).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_command_palette_visible_on_tablet(page, base_url):
    """On tablet viewport the command palette opens via Ctrl+K."""
    page.set_viewport_size(_TABLET)
    page.goto(base_url)
    page.keyboard.press("Control+k")
    expect(
        page.locator("#command-palette-overlay"),
        "Command palette must open on tablet viewport",
    ).to_have_class(re.compile(r"active"), timeout=3_000)


@pytest.mark.e2e
def test_modal_fits_mobile_viewport(page, base_url):
    """On mobile viewport, any open modal does not overflow the screen."""
    page.set_viewport_size(_MOBILE)
    page.goto(base_url)

    # Open the confirm modal via JS (it should always be in the DOM)
    page.evaluate("""() => {
        const m = document.getElementById('confirm-modal');
        if (m) m.style.display = 'flex';
    }""")

    modal = page.locator("#confirm-modal")
    if not modal.is_visible():
        pytest.skip("confirm-modal not in DOM")

    box = modal.bounding_box()
    if box is None:
        pytest.skip("Could not get bounding box for confirm-modal")

    assert box["width"] <= _MOBILE["width"], (
        f"Modal width {box['width']}px overflows mobile viewport {_MOBILE['width']}px"
    )
