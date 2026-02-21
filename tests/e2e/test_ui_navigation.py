import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_home_page_integrity(page, base_url):
    """Verify that home page loads correctly and resources are fine."""
    failed_resources = []
    page.on("requestfailed", lambda request: failed_resources.append(request.url))

    page.goto(base_url)

    # 1. Check Title (Full title from base.html)
    expect(page).to_have_title("Ollash - Local IT Agent")

    # 2. Check sidebar is visible (it's an <aside class="sidebar">)
    sidebar = page.locator("aside.sidebar")
    expect(sidebar).to_be_visible()

    # 3. Check for failed LOCAL resources (ignore CDNs for stability)
    local_failures = [r for r in failed_resources if base_url in r or "/static/" in r]
    if local_failures:
        pytest.fail(f"Local static resources failed to load: {local_failures}")
