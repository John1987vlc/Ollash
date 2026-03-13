"""
E2E SPA tests — basic page load (requires uvicorn mock server).

Tests: title, sidebar presence, no failed local static resources.
No Ollama calls are made; the server is started with OLLAMA_URL pointed at
a dead port (9999) by the flask_server fixture.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_title_is_correct(page, base_url):
    """Page title contains 'Ollash'."""
    page.goto(base_url)
    expect(page).to_have_title("Ollash - Local IT Agent")


@pytest.mark.e2e
def test_sidebar_is_visible(page, base_url):
    """The sidebar <aside> element is visible on page load."""
    page.goto(base_url)
    expect(page.locator("aside.sidebar")).to_be_visible()


@pytest.mark.e2e
def test_no_failed_local_resources(page, base_url):
    """No local /static/ resources return an error (404, 500, etc.)."""
    failed: list[str] = []
    page.on("requestfailed", lambda req: failed.append(req.url))

    # Also capture HTTP error responses for static assets
    def _on_response(response):
        if "/static/" in response.url and response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.on("response", _on_response)

    page.goto(base_url)

    local_failures = [u for u in failed if base_url in u or "/static/" in u]
    if local_failures:
        pytest.fail(f"Local static resources failed to load: {local_failures}")
