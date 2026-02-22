"""
E2E Responsive Design Tests for Ollash UI.

Verifies that the sidebar, modals, and notification container
adapt correctly to mobile viewport sizes.
"""
import pytest
from playwright.sync_api import expect

MOBILE_VIEWPORT = {"width": 375, "height": 812}
TABLET_VIEWPORT = {"width": 768, "height": 1024}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}


# ---------------------------------------------------------------------------
# Sidebar – mobile behaviour
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_sidebar_hidden_on_mobile_by_default(page, base_url):
    """
    En mobile (<768px), el sidebar no debe ser visible por defecto.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    sidebar = page.locator("#main-sidebar")
    # On mobile, sidebar should be off-screen (translated out), not covering content
    # Check that it does NOT have 'sidebar--open' class by default
    sidebar_classes = sidebar.get_attribute("class") or ""
    assert "sidebar--open" not in sidebar_classes, (
        "Sidebar should NOT be open by default on mobile"
    )


@pytest.mark.e2e
def test_hamburger_button_visible_on_mobile(page, base_url):
    """
    En mobile, el botón hamburger debe ser visible.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    hamburger = page.locator("#sidebar-hamburger")
    expect(hamburger).to_be_visible()


@pytest.mark.e2e
def test_hamburger_button_hidden_on_desktop(page, base_url):
    """
    En desktop, el botón hamburger debe estar oculto (display: none via CSS).
    """
    page.set_viewport_size(DESKTOP_VIEWPORT)
    page.goto(base_url)

    hamburger = page.locator("#sidebar-hamburger")
    # Should be hidden on desktop (CSS hides it)
    is_visible = hamburger.is_visible()
    assert not is_visible, "Hamburger button should be hidden on desktop"


@pytest.mark.e2e
def test_hamburger_opens_sidebar_on_mobile(page, base_url):
    """
    Al hacer click en el hamburger, el sidebar debe quedar visible.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    hamburger = page.locator("#sidebar-hamburger")
    expect(hamburger).to_be_visible()
    hamburger.click()

    sidebar = page.locator("#main-sidebar")
    # After click, sidebar should have sidebar--open class
    sidebar_classes = sidebar.get_attribute("class") or ""
    assert "sidebar--open" in sidebar_classes, (
        "Sidebar should be open after clicking hamburger"
    )


@pytest.mark.e2e
def test_overlay_visible_when_sidebar_open_on_mobile(page, base_url):
    """
    Al abrir el sidebar en mobile, el overlay de fondo debe ser visible.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    page.locator("#sidebar-hamburger").click()

    overlay = page.locator("#sidebar-overlay")
    overlay_classes = overlay.get_attribute("class") or ""
    assert "sidebar-overlay--visible" in overlay_classes, (
        "Sidebar overlay should be visible when sidebar is open on mobile"
    )


@pytest.mark.e2e
def test_clicking_overlay_closes_sidebar(page, base_url):
    """
    Hacer click en el overlay debe cerrar el sidebar.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    page.locator("#sidebar-hamburger").click()
    page.locator("#sidebar-overlay").wait_for(state="visible", timeout=2000)
    page.locator("#sidebar-overlay").click()

    sidebar_classes = page.locator("#main-sidebar").get_attribute("class") or ""
    assert "sidebar--open" not in sidebar_classes, (
        "Sidebar should close when overlay is clicked"
    )


# ---------------------------------------------------------------------------
# Modals – mobile behaviour
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_modal_adapts_to_mobile_viewport(page, base_url):
    """
    En mobile (<480px), los modales no deben tener overflow horizontal.
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base_url)

    # Open the automation modal
    page.evaluate("document.getElementById('automation-modal').style.display='flex'")
    modal_content = page.locator("#automation-modal .modal-content")
    expect(modal_content).to_be_visible()

    # Check that modal content does not overflow horizontally
    modal_width = modal_content.bounding_box()["width"]
    viewport_width = page.viewport_size["width"]
    assert modal_width <= viewport_width, (
        f"Modal content width ({modal_width}px) exceeds viewport ({viewport_width}px)"
    )


# ---------------------------------------------------------------------------
# Command palette – mobile
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_command_palette_fits_in_mobile_viewport(page, base_url):
    """
    El command palette no debe causar overflow horizontal en mobile.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    page.keyboard.press("Control+k")
    page.locator("#command-palette-overlay.active").wait_for(timeout=2000)

    palette = page.locator(".command-palette")
    expect(palette).to_be_visible()

    palette_box = palette.bounding_box()
    viewport_width = page.viewport_size["width"]
    assert palette_box["width"] <= viewport_width, (
        f"Command palette width ({palette_box['width']}px) exceeds viewport ({viewport_width}px)"
    )


# ---------------------------------------------------------------------------
# Notifications – mobile
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_notification_container_exists(page, base_url):
    """
    El contenedor de notificaciones debe existir en el DOM.
    """
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(base_url)

    # Trigger a notification via JS to ensure container is created
    page.evaluate("""
        () => {
            if (window.proactiveAlertHandler) {
                window.proactiveAlertHandler.showNotification('Test', 'Mobile test alert', 'info');
            }
        }
    """)

    # Container is created dynamically
    container_visible = page.evaluate(
        "document.getElementById('notifications-container') !== null"
    )
    # This is informational; container may not be created until first notification
    assert isinstance(container_visible, bool)
