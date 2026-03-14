"""
E2E SPA tests — Settings page with General/Avanzado tabs (requires uvicorn server).

Verifies the new tabbed layout:
  - 'General' tab is active by default
  - 'Avanzado' tab exists with 'Para técnicos' badge
  - Clicking a tab switches the visible panel
  - General panel shows simplified controls
  - Avanzado panel shows technical controls
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ── Helpers ──────────────────────────────────────────────────────────────────


def _navigate_to_settings(page, base_url):
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    nav = page.locator(".nav-item[data-view='settings']")
    if nav.count() == 0:
        pytest.skip("Settings nav item not found")
    nav.first.click()
    expect(page.locator("#settings-view")).to_be_visible(timeout=5_000)


# ── Tab existence & initial state ─────────────────────────────────────────────


@pytest.mark.e2e
def test_settings_has_two_tabs(page, base_url):
    """Settings page has exactly 2 tab buttons: General and Avanzado."""
    _navigate_to_settings(page, base_url)
    tabs = page.locator("#settings-view .settings-tab")
    assert tabs.count() == 2, f"Expected 2 settings tabs, found {tabs.count()}"


@pytest.mark.e2e
def test_settings_general_tab_active_by_default(page, base_url):
    """General tab has the 'active' class on page load."""
    _navigate_to_settings(page, base_url)
    general_tab = page.locator("#settings-view .settings-tab[data-tab='general']")
    expect(general_tab).to_be_visible(timeout=3_000)
    expect(general_tab).to_have_class(__import__("re").compile(r"active"), timeout=3_000)


@pytest.mark.e2e
def test_settings_advanced_tab_has_badge(page, base_url):
    """Avanzado tab has a .tab-badge element with 'técnicos' text."""
    _navigate_to_settings(page, base_url)
    advanced_tab = page.locator("#settings-view .settings-tab[data-tab='advanced']")
    expect(advanced_tab).to_be_visible(timeout=3_000)
    badge = advanced_tab.locator(".tab-badge")
    expect(badge).to_be_visible(timeout=3_000)
    badge_text = badge.text_content() or ""
    assert "técnicos" in badge_text.lower(), f"Expected badge with 'técnicos', got '{badge_text}'"


# ── General tab panel ─────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_settings_general_panel_visible_by_default(page, base_url):
    """#settings-tab-general panel is visible when settings page opens."""
    _navigate_to_settings(page, base_url)
    panel = page.locator("#settings-tab-general")
    expect(panel).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_settings_general_panel_has_ollama_url_input(page, base_url):
    """General tab shows the Ollama URL input."""
    _navigate_to_settings(page, base_url)
    url_input = page.locator("#settings-tab-general #config-ollama-url")
    expect(url_input).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_settings_general_panel_has_model_selector(page, base_url):
    """General tab shows the model selector dropdown with friendly names."""
    _navigate_to_settings(page, base_url)
    selector = page.locator("#settings-tab-general #config-model-selector")
    expect(selector).to_be_visible(timeout=3_000)
    # Should have multiple options
    options = selector.locator("option")
    count = options.count()
    assert count >= 3, f"Expected at least 3 model options, found {count}"


@pytest.mark.e2e
def test_settings_general_model_options_have_friendly_names(page, base_url):
    """Model selector options use plain language names (Rápido, Equilibrado, Potente)."""
    _navigate_to_settings(page, base_url)
    selector = page.locator("#settings-tab-general #config-model-selector")
    expect(selector).to_be_visible(timeout=3_000)
    all_options_text = selector.inner_text()
    assert any(word in all_options_text for word in ("Rápido", "Equilibrado", "Potente")), (
        f"Model options should have friendly names. Got: '{all_options_text}'"
    )


@pytest.mark.e2e
def test_settings_general_panel_has_theme_selector(page, base_url):
    """General tab shows the theme selector (Oscuro/Claro)."""
    _navigate_to_settings(page, base_url)
    theme_sel = page.locator("#settings-tab-general #config-theme-selector")
    expect(theme_sel).to_be_visible(timeout=3_000)
    theme_text = theme_sel.inner_text()
    assert "Oscuro" in theme_text or "Claro" in theme_text, (
        f"Theme selector should have Oscuro/Claro options. Got: '{theme_text}'"
    )


# ── Advanced tab panel ────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_settings_advanced_panel_hidden_by_default(page, base_url):
    """#settings-tab-advanced panel is hidden until the tab is clicked."""
    _navigate_to_settings(page, base_url)
    panel = page.locator("#settings-tab-advanced")
    expect(panel).to_be_hidden(timeout=3_000)


@pytest.mark.e2e
def test_settings_switching_to_advanced_tab(page, base_url):
    """Clicking 'Avanzado' tab shows the advanced panel and hides general."""
    _navigate_to_settings(page, base_url)
    advanced_tab = page.locator("#settings-view .settings-tab[data-tab='advanced']")
    advanced_tab.click()
    page.wait_for_timeout(300)

    expect(page.locator("#settings-tab-advanced")).to_be_visible(timeout=3_000)
    expect(page.locator("#settings-tab-general")).to_be_hidden(timeout=3_000)


@pytest.mark.e2e
def test_settings_advanced_panel_has_llm_params(page, base_url):
    """Avanzado panel contains LLM parameters (temperature, context window)."""
    _navigate_to_settings(page, base_url)
    page.locator("#settings-view .settings-tab[data-tab='advanced']").click()
    page.wait_for_timeout(300)

    advanced = page.locator("#settings-tab-advanced")
    # Temperature slider or context window select must be present
    has_range = advanced.locator("input[type='range']").count() > 0
    has_context = advanced.locator("select").count() > 0
    assert has_range or has_context, "Avanzado panel should contain LLM parameter controls"


@pytest.mark.e2e
def test_settings_advanced_panel_has_mermaid_theme(page, base_url):
    """Avanzado panel contains the Mermaid diagram theme selector."""
    _navigate_to_settings(page, base_url)
    page.locator("#settings-view .settings-tab[data-tab='advanced']").click()
    page.wait_for_timeout(300)

    mermaid_sel = page.locator("#settings-tab-advanced #mermaid-theme-selector")
    expect(mermaid_sel).to_be_visible(timeout=3_000)


# ── Tab switching round-trip ──────────────────────────────────────────────────


@pytest.mark.e2e
def test_settings_tab_roundtrip(page, base_url):
    """Switching General → Avanzado → General restores the General panel."""
    _navigate_to_settings(page, base_url)
    general_tab = page.locator("#settings-view .settings-tab[data-tab='general']")
    advanced_tab = page.locator("#settings-view .settings-tab[data-tab='advanced']")

    # Switch to advanced
    advanced_tab.click()
    page.wait_for_timeout(300)
    expect(page.locator("#settings-tab-advanced")).to_be_visible(timeout=3_000)

    # Switch back to general
    general_tab.click()
    page.wait_for_timeout(300)
    expect(page.locator("#settings-tab-general")).to_be_visible(timeout=3_000)
    expect(page.locator("#settings-tab-advanced")).to_be_hidden(timeout=3_000)


# ── No JS errors ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_settings_tabs_no_js_errors(page, base_url):
    """Interacting with settings tabs produces no JavaScript errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    _navigate_to_settings(page, base_url)
    page.locator("#settings-view .settings-tab[data-tab='advanced']").click()
    page.wait_for_timeout(300)
    page.locator("#settings-view .settings-tab[data-tab='general']").click()
    page.wait_for_timeout(300)
    assert not errors, f"JS errors while interacting with settings tabs: {errors}"
