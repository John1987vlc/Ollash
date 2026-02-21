import pytest
import json
import re
from playwright.sync_api import expect


@pytest.mark.e2e
def test_project_wizard_flow(page, base_url):
    """
    Validates the multi-step project creation wizard.
    """
    page.goto(base_url)
    page.locator(".nav-item[data-view='create']").click()

    # Wait for the wizard view
    expect(page.locator("#create-view")).to_be_visible()

    # --- Step 1: Project Identity ---
    page.locator("#project-name").fill("E2E-Wizard-Project")

    # Click Next
    page.locator("#wizard-next-1").click()

    # --- Step 2: Configuration ---
    # Wait for step 2 to be active
    expect(page.locator("#wizard-step-2")).to_have_class(re.compile(r"active"))

    # Click Next
    page.locator("#wizard-next-2").click()

    # --- Step 3: Description ---
    expect(page.locator("#wizard-step-3")).to_have_class(re.compile(r"active"))
    page.locator("#project-description").fill("A project generated via E2E test.")

    # Mock the Generation API - Matching the structure expected by StructureEditor.js
    mock_data = {
        "status": "structure_generated",
        "project_name": "E2E-Wizard-Project",
        "structure": {"name": "root", "folders": [], "files": ["README.md", "main.py"]},
    }

    page.route(
        "**/api/projects/generate_structure",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_data)),
    )

    # Click Generate
    page.locator("#wizard-generate").click()

    # Verify we transitioned to the structure review section
    expect(page.locator("#generated-structure-section")).to_be_visible(timeout=10000)

    # Verify the structure editor rendered the mock files
    expect(page.locator("#structure-editor-tree")).to_contain_text("README.md")
    expect(page.locator("#structure-editor-tree")).to_contain_text("main.py")
