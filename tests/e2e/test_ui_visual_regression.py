"""Visual regression tests using Playwright snapshot comparisons.

On first run (or with --update-snapshots), Playwright takes baseline screenshots
and stores them in ``tests/e2e/snapshots/``. On subsequent runs the screenshots
are compared pixel-by-pixel within the configured tolerance.

Usage:
    # Generate / update baselines
    pytest tests/e2e/test_ui_visual_regression.py --update-snapshots

    # Regular CI run (compare against baselines)
    pytest tests/e2e/test_ui_visual_regression.py
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e

# Maximum number of differing pixels before the test fails.
# Allows for minor font-rendering differences across OS / GPU.
MAX_DIFF_PIXELS = 150


@pytest.fixture(autouse=True)
def _stable_viewport(page):
    """Fix viewport to a consistent size for all visual regression tests."""
    page.set_viewport_size({"width": 1280, "height": 800})


def test_home_page_visual(page, base_url, flask_server):
    """Home / dashboard page layout must match the stored baseline."""
    page.goto(f"{base_url}/", wait_until="networkidle")
    # Wait for any CSS transitions or loaders to finish
    page.wait_for_timeout(500)
    expect(page).to_have_screenshot(
        "home-page.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_chat_page_visual(page, base_url, flask_server):
    """Chat page layout must match the stored baseline."""
    page.goto(f"{base_url}/chat", wait_until="networkidle")
    page.wait_for_timeout(500)
    expect(page).to_have_screenshot(
        "chat-page.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_settings_page_visual(page, base_url, flask_server):
    """Settings page layout must match the stored baseline."""
    page.goto(f"{base_url}/settings", wait_until="networkidle")
    page.wait_for_timeout(500)
    expect(page).to_have_screenshot(
        "settings-page.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_docs_page_visual(page, base_url, flask_server):
    """Documentation page layout must match the stored baseline."""
    page.goto(f"{base_url}/docs", wait_until="networkidle")
    page.wait_for_timeout(500)
    expect(page).to_have_screenshot(
        "docs-page.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_benchmark_page_visual(page, base_url, flask_server):
    """Benchmark page layout must match the stored baseline."""
    page.goto(f"{base_url}/benchmark", wait_until="networkidle")
    page.wait_for_timeout(500)
    expect(page).to_have_screenshot(
        "benchmark-page.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_sidebar_visual(page, base_url, flask_server):
    """Sidebar navigation component must match the stored baseline."""
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.wait_for_timeout(300)

    sidebar = page.locator(".sidebar")
    expect(sidebar).to_have_screenshot(
        "sidebar-component.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_dark_theme_home_visual(page, base_url, flask_server):
    """Home page in dark theme (default) must match baseline."""
    page.goto(f"{base_url}/", wait_until="networkidle")
    # Ensure dark theme is active (default)
    page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
    page.wait_for_timeout(300)
    expect(page).to_have_screenshot(
        "home-dark-theme.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )


def test_light_theme_home_visual(page, base_url, flask_server):
    """Home page in light theme must match baseline.

    This test verifies that the CSS variable swap for ``[data-theme='light']``
    applies correctly across all components.
    """
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.evaluate("document.documentElement.setAttribute('data-theme', 'light')")
    page.wait_for_timeout(400)  # Allow CSS transition to complete
    expect(page).to_have_screenshot(
        "home-light-theme.png",
        max_diff_pixels=MAX_DIFF_PIXELS,
    )
