"""
E2E Accessibility Tests for Ollash UI.

Verifies that ARIA attributes added in the UI/UX improvements are present
and that keyboard navigation works correctly.
"""
import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Modal ARIA attributes
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_automation_modal_has_aria_dialog(page, base_url):
    """
    El modal de automatización debe tener role='dialog' y aria-modal='true'
    cuando está abierto, y un aria-labelledby apuntando al título correcto.
    """
    page.goto(base_url)

    # Open automation modal via JS (simulating the button click)
    page.evaluate("document.getElementById('automation-modal').style.display='flex'")

    modal = page.locator("#automation-modal")
    expect(modal).to_be_visible()

    role = page.evaluate("document.getElementById('automation-modal').getAttribute('role')")
    aria_modal = page.evaluate("document.getElementById('automation-modal').getAttribute('aria-modal')")
    labelledby = page.evaluate("document.getElementById('automation-modal').getAttribute('aria-labelledby')")

    assert role == "dialog", f"Expected role='dialog' but got '{role}'"
    assert aria_modal == "true", f"Expected aria-modal='true' but got '{aria_modal}'"
    assert labelledby is not None, "Modal should have aria-labelledby referencing its title"

    # Verify the referenced element exists and has text
    title_text = page.evaluate(
        f"document.getElementById('{labelledby}') ? document.getElementById('{labelledby}').textContent : null"
    )
    assert title_text and len(title_text.strip()) > 0, "aria-labelledby must point to a non-empty title element"


@pytest.mark.e2e
def test_confirm_modal_has_aria_dialog(page, base_url):
    """
    El modal de confirmación genérico debe tener role='dialog' y aria-modal='true'.
    """
    page.goto(base_url)
    page.evaluate("document.getElementById('confirm-modal').style.display='flex'")

    role = page.evaluate("document.getElementById('confirm-modal').getAttribute('role')")
    aria_modal = page.evaluate("document.getElementById('confirm-modal').getAttribute('aria-modal')")

    assert role == "dialog"
    assert aria_modal == "true"


@pytest.mark.e2e
def test_all_modals_have_dialog_role(page, base_url):
    """
    Todos los modals globales deben tener role='dialog'.
    """
    page.goto(base_url)

    modal_ids = [
        "test-gen-modal",
        "automation-modal",
        "notification-config-modal",
        "image-editor-modal",
        "diff-modal",
        "swarm-modal",
        "benchmark-modal",
        "hil-modal",
        "confirm-modal",
    ]

    missing_role = []
    for modal_id in modal_ids:
        role = page.evaluate(
            f"document.getElementById('{modal_id}') ? document.getElementById('{modal_id}').getAttribute('role') : 'MISSING_ELEMENT'"
        )
        if role != "dialog":
            missing_role.append(f"{modal_id}: role='{role}'")

    assert not missing_role, f"Modals without role='dialog': {missing_role}"


# ---------------------------------------------------------------------------
# Close button aria-label
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_modal_close_buttons_have_aria_label(page, base_url):
    """
    Los botones de cierre de modales deben tener aria-label no vacío.
    """
    page.goto(base_url)

    close_buttons = page.locator(".close-modal")
    count = close_buttons.count()
    assert count > 0, "Should find at least one .close-modal button"

    for i in range(count):
        btn = close_buttons.nth(i)
        aria_label = btn.get_attribute("aria-label")
        assert aria_label and len(aria_label.strip()) > 0, (
            f"Close button #{i} is missing aria-label"
        )


# ---------------------------------------------------------------------------
# Sidebar ARIA
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_sidebar_nav_has_aria_label(page, base_url):
    """
    El elemento <nav class='sidebar-nav'> debe tener aria-label.
    """
    page.goto(base_url)
    nav = page.locator("nav.sidebar-nav")
    expect(nav).to_be_visible()

    aria_label = nav.get_attribute("aria-label")
    assert aria_label and len(aria_label.strip()) > 0, "Sidebar nav must have aria-label"


@pytest.mark.e2e
def test_nav_group_headers_have_aria_expanded(page, base_url):
    """
    Los botones de cabecera de grupo nav deben tener aria-expanded.
    """
    page.goto(base_url)

    headers = page.locator(".nav-group-header")
    count = headers.count()
    assert count > 0, "Should find nav group headers"

    for i in range(count):
        hdr = headers.nth(i)
        aria_expanded = hdr.get_attribute("aria-expanded")
        assert aria_expanded in ("true", "false"), (
            f"nav-group-header #{i} must have aria-expanded='true' or 'false', got '{aria_expanded}'"
        )


@pytest.mark.e2e
def test_toggle_pair_mode_has_aria_label(page, base_url):
    """
    El botón #toggle-pair-mode debe tener aria-label.
    """
    page.goto(base_url)
    btn = page.locator("#toggle-pair-mode")
    expect(btn).to_be_visible()

    aria_label = btn.get_attribute("aria-label")
    assert aria_label and len(aria_label.strip()) > 0, "#toggle-pair-mode must have aria-label"


# ---------------------------------------------------------------------------
# Command Palette focus trap
# ---------------------------------------------------------------------------

import re


@pytest.mark.e2e
def test_command_palette_opens_on_ctrl_k(page, base_url):
    """
    El command palette debe abrirse con Ctrl+K.
    """
    page.goto(base_url)
    page.keyboard.press("Control+k")

    overlay = page.locator("#command-palette-overlay")
    expect(overlay).to_have_class(re.compile("active"))


@pytest.mark.e2e
def test_command_palette_has_aria_dialog(page, base_url):
    """
    El overlay del command palette debe tener role='dialog' cuando está activo.
    """
    page.goto(base_url)
    page.keyboard.press("Control+k")

    overlay = page.locator("#command-palette-overlay")
    expect(overlay).to_have_class(re.compile("active"))

    role = overlay.get_attribute("role")
    aria_modal = overlay.get_attribute("aria-modal")
    assert role == "dialog", f"Expected role='dialog' on command palette, got '{role}'"
    assert aria_modal == "true", f"Expected aria-modal='true', got '{aria_modal}'"


@pytest.mark.e2e
def test_command_palette_input_focused_on_open(page, base_url):
    """
    Al abrir el command palette, el foco debe estar en el input.
    """
    page.goto(base_url)
    page.keyboard.press("Control+k")

    # Wait for the palette to open
    page.locator("#command-palette-overlay.active").wait_for(timeout=2000)

    focused_id = page.evaluate("document.activeElement ? document.activeElement.id : null")
    assert focused_id == "command-palette-input", (
        f"Focus should be on command-palette-input, but it's on '{focused_id}'"
    )


@pytest.mark.e2e
def test_command_palette_closes_on_escape(page, base_url):
    """
    Escape debe cerrar el command palette.
    """
    page.goto(base_url)
    page.keyboard.press("Control+k")
    page.locator("#command-palette-overlay.active").wait_for(timeout=2000)

    page.keyboard.press("Escape")
    overlay = page.locator("#command-palette-overlay")
    expect(overlay).not_to_have_class(re.compile("active"))


# ---------------------------------------------------------------------------
# Focus-visible indicator
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_focus_visible_style_exists(page, base_url):
    """
    La regla :focus-visible debe estar definida en el CSS global.
    """
    page.goto(base_url)

    has_focus_visible = page.evaluate("""
        () => {
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules || []) {
                        if (rule.selectorText && rule.selectorText.includes(':focus-visible')) {
                            return true;
                        }
                    }
                } catch (e) { /* cross-origin */ }
            }
            return false;
        }
    """)
    assert has_focus_visible, ":focus-visible CSS rule must be defined in global styles"
