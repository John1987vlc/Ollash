"""
E2E SPA tests — Help & Guides page (requires uvicorn mock server).

Verifies that the new help page:
  - Renders when clicking the 'Ayuda y Guías' nav item
  - Contains all required sections (qué es, primeros pasos, casos, FAQ, etc.)
  - FAQ accordion works with native <details>/<summary>
  - 'Ir a Configuración' CTA button navigates to settings view
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ── Helpers ──────────────────────────────────────────────────────────────────


def _navigate_to_help(page, base_url):
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    help_nav = page.locator(".nav-item[data-view='help']")
    if help_nav.count() == 0:
        pytest.skip("'Ayuda y Guías' nav item not found in sidebar")
    help_nav.first.click()
    expect(page.locator("#help-view")).to_be_visible(timeout=5_000)


# ── Visibility & routing ──────────────────────────────────────────────────────


@pytest.mark.e2e
def test_help_view_renders_on_nav_click(page, base_url):
    """Clicking 'Ayuda y Guías' makes #help-view visible."""
    _navigate_to_help(page, base_url)
    expect(page.locator("#help-view")).to_be_visible()


@pytest.mark.e2e
def test_help_view_has_page_title(page, base_url):
    """Help page displays an h1 containing 'Ayuda'."""
    _navigate_to_help(page, base_url)
    h1 = page.locator("#help-view h1")
    expect(h1).to_be_visible(timeout=3_000)
    text = h1.text_content() or ""
    assert "Ayuda" in text, f"Expected h1 with 'Ayuda', got '{text}'"


# ── Required sections ─────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_help_page_contains_que_es_section(page, base_url):
    """Help page contains '¿Qué es Ollash?' section."""
    _navigate_to_help(page, base_url)
    section = page.locator("#help-que-es")
    expect(section).to_be_visible(timeout=3_000)
    expect(section).to_contain_text("Ollash")


@pytest.mark.e2e
def test_help_page_contains_primeros_pasos_section(page, base_url):
    """Help page contains 'Primeros pasos' section with numbered steps."""
    _navigate_to_help(page, base_url)
    section = page.locator("#help-primeros-pasos")
    expect(section).to_be_visible(timeout=3_000)
    steps = section.locator(".help-step")
    count = steps.count()
    assert count >= 4, f"Expected at least 4 steps in 'Primeros pasos', found {count}"


@pytest.mark.e2e
def test_help_page_contains_use_case_grid(page, base_url):
    """Help page has at least 4 practical use case cards."""
    _navigate_to_help(page, base_url)
    cards = page.locator("#help-casos .help-use-case-card")
    count = cards.count()
    assert count >= 4, f"Expected at least 4 use-case cards, found {count}"


@pytest.mark.e2e
def test_help_page_contains_proyecto_section(page, base_url):
    """Help page has a 'Crear tu primer proyecto' walkthrough section."""
    _navigate_to_help(page, base_url)
    section = page.locator("#help-proyecto")
    expect(section).to_be_visible(timeout=3_000)
    expect(section).to_contain_text("proyecto")


@pytest.mark.e2e
def test_help_page_contains_faq_section(page, base_url):
    """Help page has at least 5 FAQ items using <details>/<summary>."""
    _navigate_to_help(page, base_url)
    faqs = page.locator("#help-faq details.help-faq-item")
    count = faqs.count()
    assert count >= 5, f"Expected at least 5 FAQ items, found {count}"


@pytest.mark.e2e
def test_help_page_has_config_cta_button(page, base_url):
    """Help page has a 'Ir a Configuración' CTA button."""
    _navigate_to_help(page, base_url)
    cta = page.locator("#help-config button[data-view='settings']")
    expect(cta).to_be_visible(timeout=3_000)
    text = cta.text_content() or ""
    assert "Configuraci" in text, f"Expected CTA button text with 'Configuración', got '{text}'"


# ── FAQ accordion ─────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_faq_item_expands_on_click(page, base_url):
    """Clicking a <summary> inside a <details> opens the FAQ answer."""
    _navigate_to_help(page, base_url)
    first_faq = page.locator("#help-faq details.help-faq-item").first
    expect(first_faq).to_be_visible(timeout=3_000)

    # Initially closed
    is_open = first_faq.get_attribute("open")
    assert is_open is None, "First FAQ item should be closed initially"

    # Click the summary to open
    first_faq.locator("summary").click()
    page.wait_for_timeout(200)

    is_open_after = first_faq.get_attribute("open")
    assert is_open_after is not None, "FAQ item should have 'open' attribute after clicking summary"


@pytest.mark.e2e
def test_faq_item_collapses_on_second_click(page, base_url):
    """Clicking an open FAQ summary closes it again."""
    _navigate_to_help(page, base_url)
    summary = page.locator("#help-faq details.help-faq-item summary").first
    # Open it
    summary.click()
    page.wait_for_timeout(200)
    # Close it
    summary.click()
    page.wait_for_timeout(200)

    parent = page.locator("#help-faq details.help-faq-item").first
    assert parent.get_attribute("open") is None, "FAQ item should be closed after second click"


@pytest.mark.e2e
def test_multiple_faq_items_can_be_open_simultaneously(page, base_url):
    """Multiple FAQ items can be open at the same time (native <details> behavior)."""
    _navigate_to_help(page, base_url)
    faqs = page.locator("#help-faq details.help-faq-item")
    if faqs.count() < 2:
        pytest.skip("Need at least 2 FAQ items for this test")

    faqs.nth(0).locator("summary").click()
    faqs.nth(1).locator("summary").click()
    page.wait_for_timeout(300)

    assert faqs.nth(0).get_attribute("open") is not None, "First FAQ should be open"
    assert faqs.nth(1).get_attribute("open") is not None, "Second FAQ should be open"


# ── CTA navigation ────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_help_cta_navigates_to_settings(page, base_url):
    """Clicking 'Ir a Configuración' in help page shows the settings view."""
    _navigate_to_help(page, base_url)
    cta = page.locator("#help-config button[data-view='settings']")
    expect(cta).to_be_visible(timeout=3_000)
    cta.click()
    page.wait_for_timeout(500)
    settings_view = page.locator("#settings-view")
    expect(settings_view).to_be_visible(timeout=5_000)


# ── Content integrity ─────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_help_page_mentions_ollama(page, base_url):
    """Help page text mentions Ollama (key dependency for users to understand)."""
    _navigate_to_help(page, base_url)
    help_view = page.locator("#help-view")
    expect(help_view).to_contain_text("Ollama")


@pytest.mark.e2e
def test_help_page_has_no_js_errors(page, base_url):
    """Navigating to the help page produces no JavaScript page errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    _navigate_to_help(page, base_url)
    assert not errors, f"JS errors on help page: {errors}"
