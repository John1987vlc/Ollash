import pytest
from playwright.sync_api import expect

# These tests require a running server and Playwright browser — skip in unit test runs.
pytestmark = pytest.mark.skip(reason="E2E test: requires running server + Playwright browser")


@pytest.mark.e2e
def test_sandbox_ui_initialization(page, base_url):
    """Test that the sandbox view loads and initializes Monaco."""
    page.goto(base_url)

    # Navigate to sandbox
    page.locator(".nav-item[data-view='sandbox']").click()

    # Check view is active
    expect(page.locator("#sandbox-view")).to_be_visible()

    # Check Monaco container exists
    expect(page.locator("#monaco-editor-container")).to_be_visible()

    # Wait for Monaco to load (it injects an iframe or many divs)
    page.wait_for_selector(".monaco-editor", timeout=10000)

    # Check if we can see default code (this is tricky with Monaco, but we can check the window object)
    editor_exists = page.evaluate("window.ollashSandboxEditor !== null")
    assert editor_exists is True


@pytest.mark.e2e
def test_sandbox_execution_error_no_code(page, base_url):
    """Test error handling when trying to run empty code."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='sandbox']").click()

    # Clear editor
    page.evaluate("window.ollashSandboxEditor.setValue('')")

    # Click run
    page.locator("#run-sandbox-btn").click()

    # Check error message
    expect(page.locator("#output-content")).to_contain_text("Error: No code to execute")
