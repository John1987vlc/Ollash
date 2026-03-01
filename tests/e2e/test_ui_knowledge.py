import pytest
import re
from playwright.sync_api import expect


@pytest.mark.e2e
def test_knowledge_view_loads(page, base_url):
    """Verifies that the Knowledge Base (Intelligence Hub) view loads correctly."""
    page.goto(base_url)

    # 1. Expand 'Memoria y Conocimiento' group if needed
    header = page.locator("button[aria-controls='nav-group-memoria']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        page.wait_for_timeout(300)

    # 2. Click on 'Knowledge Base' nav item
    page.locator(".nav-item[data-view='knowledge']").click()

    # 3. Verify the view container becomes active
    expect(page.locator("#knowledge-view")).to_be_visible()
    expect(page.locator("#knowledge-view")).to_have_class(re.compile(r"(^|\s)active(\s|$)"))

    # 4. Verify title and description
    expect(page.locator("#knowledge-view h1")).to_have_text("Intelligence Hub")
    expect(page.locator("#knowledge-view p").first).to_contain_text("Explore the agent's knowledge workspace")

    # 5. Verify tabs are present
    expect(page.locator(".k-tab:has-text('Vector Documents')")).to_be_visible()
    expect(page.locator(".k-tab:has-text('Episodic Memory')")).to_be_visible()
    expect(page.locator(".k-tab:has-text('Error Immunity')")).to_be_visible()

    # 6. Verify vector tab is active by default
    expect(page.locator("#vector-tab")).to_be_visible()
    expect(page.locator("#vector-tab")).to_have_class(re.compile(r"(^|\s)active(\s|$)"))

    # 7. Check for placeholder or documents (since it's a fresh test, likely placeholder)
    # The loadVectorDocs fetch will happen now.
    # If it fails with 500, we might see the error message in the console or UI.

    # Wait for fetch to complete (or fail)
    page.wait_for_timeout(1000)

    # If the 500 error happens, the JS should handle it and show "Failed to load"
    # based on my previous read of knowledge.js
    # kbDocGrid.innerHTML = '<p class="placeholder">Failed to load knowledge base.</p>';

    # Verify we are NOT seeing the "Failed to load" message
    expect(page.locator("#kb-doc-grid")).not_to_contain_text("Failed to load knowledge base.")

    # It should either show "No documents indexed yet." or actual documents.
    expect(page.locator("#kb-doc-grid")).to_be_visible()
